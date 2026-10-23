#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

#[tauri::command]
fn open_approved_url(app: tauri::AppHandle, value: String) -> Result<(), String> {
    let parsed = url::Url::parse(&value).map_err(|_| "Invalid external URL".to_string())?;
    if parsed.scheme() != "https" || parsed.port_or_known_default() != Some(443) {
        return Err("Only approved HTTPS links can be opened externally".to_string());
    }
    let Some(host) = parsed.host_str().map(str::to_ascii_lowercase) else {
        return Err("External URL has no host".to_string());
    };
    let mut approved_hosts = vec!["b2-b-crm.vercel.app".to_string()];
    if let Some(api_base) = option_env!("VITE_API_BASE_URL") {
        if let Ok(api_url) = url::Url::parse(api_base) {
            if let Some(api_host) = api_url.host_str() {
                approved_hosts.push(api_host.to_ascii_lowercase());
            }
        }
    }
    if let Some(extra_hosts) = option_env!("VITE_EXTERNAL_LINK_HOSTS") {
        approved_hosts.extend(extra_hosts.split(',').map(|host| host.trim().to_ascii_lowercase()).filter(|host| !host.is_empty()));
    }
    if !approved_hosts.iter().any(|approved| approved == &host) {
        return Err("External destination is not approved".to_string());
    }
    use tauri_plugin_opener::OpenerExt;
    app.opener().open_url(parsed.to_string(), None::<&str>).map_err(|_| "Unable to open external link".to_string())
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::Builder::new().open_js_links_on_click(false).build())
        .invoke_handler(tauri::generate_handler![open_approved_url])
        .run(tauri::generate_context!())
        .expect("failed to run B2B CRM desktop application");
}
