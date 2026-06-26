use std::net::TcpListener;
use std::process::{Child, Command};
use std::sync::Mutex;
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
    // In production: the PyInstaller binary is bundled as a sidecar next to the app.
    // In dev: fall back to running uvicorn directly via the venv Python.
    let resource_dir = app
        .path()
        .resource_dir()
        .expect("failed to get resource dir");

    #[cfg(target_os = "windows")]
    let bin_name = "alsoenergy-backend.exe";
    #[cfg(not(target_os = "windows"))]
    let bin_name = "alsoenergy-backend";

    resource_dir.join(bin_name)
}

fn spawn_backend(port: u16, app: &tauri::AppHandle) -> Child {
    let bin = backend_binary_path(app);

    if bin.exists() {
        // Production: run the PyInstaller binary
        Command::new(&bin)
            .args(["--port", &port.to_string()])
            .spawn()
            .unwrap_or_else(|e| panic!("failed to spawn backend binary {bin:?}: {e}"))
    } else {
        // Dev fallback: run uvicorn from the backend venv
        let project_root = std::env::current_dir()
            .expect("failed to get cwd")
            .parent()
            .expect("no parent of frontend dir")
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
            .unwrap_or_else(|e| panic!("failed to spawn dev uvicorn {python:?}: {e}"))
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let port = find_free_port();

    tauri::Builder::default()
        .plugin(tauri_plugin_log::Builder::default().level(log::LevelFilter::Info).build())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .manage(BackendState(Mutex::new(None)))
        .setup(move |app| {
            // Spawn backend and store the handle for cleanup
            let child = spawn_backend(port, app.handle());
            *app.state::<BackendState>().0.lock().unwrap() = Some(child);

            // Inject the port into the webview so the frontend can reach the backend
            let webview = app.get_webview_window("main").unwrap();
            webview
                .eval(&format!("window.__BACKEND_PORT__ = {port};"))
                .ok();

            log::info!("Backend spawned on port {port}");
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error building tauri app")
        .run(|app, event| {
            if let RunEvent::Exit = event {
                // Kill the backend child process on exit
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
