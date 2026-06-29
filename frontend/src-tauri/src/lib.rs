use std::net::TcpListener;
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::{Duration, Instant};
use tauri::{Manager, RunEvent};

pub struct BackendState(pub Mutex<Option<Child>>);

fn find_free_port() -> u16 {
    TcpListener::bind("127.0.0.1:0")
        .expect("failed to bind to find a free port")
        .local_addr()
        .unwrap()
        .port()
}

fn backend_binary_path(app: &tauri::AppHandle) -> std::path::PathBuf {
    let resource_dir = app
        .path()
        .resource_dir()
        .expect("failed to get resource dir");

    // onedir bundle: the exe lives inside an alsoenergy-backend/ subfolder.
    #[cfg(target_os = "windows")]
    let bin_name = "alsoenergy-backend.exe";
    #[cfg(not(target_os = "windows"))]
    let bin_name = "alsoenergy-backend";

    resource_dir.join("alsoenergy-backend").join(bin_name)
}

fn spawn_backend(port: u16, app: &tauri::AppHandle) -> Result<Child, String> {
    let bin = backend_binary_path(app);

    if bin.exists() {
        log::info!("Spawning production backend: {:?}", bin);
        Command::new(&bin)
            .args(["--port", &port.to_string()])
            .spawn()
            .map_err(|e| format!("Failed to spawn backend binary {:?}: {}", bin, e))
    } else {
        log::info!("Production binary not found at {:?}, falling back to dev uvicorn", bin);

        let project_root = std::env::current_dir()
            .map_err(|e| format!("Failed to get cwd: {}", e))?
            .parent()
            .ok_or("No parent of frontend dir")?
            .to_path_buf();

        #[cfg(target_os = "windows")]
        let python = project_root.join("backend").join(".venv").join("Scripts").join("python.exe");
        #[cfg(not(target_os = "windows"))]
        let python = project_root.join("backend").join(".venv").join("bin").join("python");

        Command::new(&python)
            .args([
                "-m", "uvicorn",
                "app.main:app",
                "--host", "127.0.0.1",
                "--port", &port.to_string(),
            ])
            .current_dir(project_root.join("backend"))
            .spawn()
            .map_err(|e| format!("Failed to spawn dev uvicorn {:?}: {}", python, e))
    }
}

/// Inject the backend port into the webview with retries so we don't miss a race
/// between the webview initialising and setup() running.
fn inject_port(app: &tauri::AppHandle, port: u16) {
    let js = format!("window.__BACKEND_PORT__ = {};", port);
    for attempt in 0..10u32 {
        if let Some(webview) = app.get_webview_window("main") {
            match webview.eval(&js) {
                Ok(()) => {
                    log::info!("Injected __BACKEND_PORT__ = {} (attempt {})", port, attempt + 1);
                    return;
                }
                Err(e) => log::warn!("eval attempt {} failed: {}", attempt + 1, e),
            }
        }
        std::thread::sleep(Duration::from_millis(200));
    }
    log::error!("Failed to inject __BACKEND_PORT__ after 10 attempts — frontend will not reach the backend");
}

/// Poll the health endpoint until it responds or the timeout elapses.
/// Returns an error message if the backend never becomes ready.
fn wait_for_backend(port: u16, timeout: Duration) -> Result<(), String> {
    let url = format!("http://127.0.0.1:{}/api/health", port);
    let deadline = Instant::now() + timeout;

    loop {
        match ureq::get(&url).call() {
            Ok(_) => {
                log::info!("Backend ready on port {}", port);
                return Ok(());
            }
            Err(e) => log::debug!("Backend not ready: {}", e),
        }

        if Instant::now() >= deadline {
            return Err(format!(
                "Backend did not become ready on port {} within {:?}",
                port, timeout
            ));
        }

        std::thread::sleep(Duration::from_millis(500));
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let port = find_free_port();

    tauri::Builder::default()
        .plugin(
            tauri_plugin_log::Builder::default()
                .level(log::LevelFilter::Info)
                // Write a log file so Windows users can share it for debugging.
                .target(tauri_plugin_log::Target::new(
                    tauri_plugin_log::TargetKind::LogDir {
                        file_name: Some("export-tool-backend".into()),
                    },
                ))
                .build(),
        )
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .manage(BackendState(Mutex::new(None)))
        .setup(move |app| {
            let handle = app.handle().clone();

            match spawn_backend(port, &handle) {
                Err(e) => {
                    log::error!("Backend spawn failed: {}", e);
                    // Show a dialog so the error is visible on Windows.
                    tauri_plugin_dialog::DialogExt::dialog(&handle)
                        .message(format!(
                            "The backend process could not start.\n\n{}\n\nCheck the log file for details.",
                            e
                        ))
                        .title("Backend Error")
                        .blocking_show();
                }
                Ok(child) => {
                    *app.state::<BackendState>().0.lock().unwrap() = Some(child);
                    log::info!("Backend process spawned on port {}", port);

                    // Inject the port immediately so the frontend's startup-poll loop
                    // hits the right URL while the backend is still warming up.
                    inject_port(app.handle(), port);

                    // Health-check in a background thread. If the backend never becomes
                    // ready we show an error dialog; otherwise this is just logging.
                    let app_handle = app.handle().clone();
                    std::thread::spawn(move || {
                        // PyInstaller bundles on Windows can take 30+ s to unpack.
                        if let Err(e) = wait_for_backend(port, Duration::from_secs(90)) {
                            log::error!("Backend readiness timeout: {}", e);
                            tauri_plugin_dialog::DialogExt::dialog(&app_handle)
                                .message(format!(
                                    "The backend started but did not become ready.\n\n{}\n\nCheck the log file for details.",
                                    e
                                ))
                                .title("Backend Error")
                                .blocking_show();
                        }
                    });
                }
            }

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error building tauri app")
        .run(|app, event| {
            if let RunEvent::Exit = event {
                if let Some(mut child) = app
                    .state::<BackendState>()
                    .0
                    .lock()
                    .unwrap()
                    .take()
                {
                    child.kill().ok();
                }
            }
        });
}
