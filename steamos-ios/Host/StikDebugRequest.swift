import Foundation

// StikDebug 3.1.10 HomeView handles this route, bundle-id, pid and script-name.
// No framework, pairing file or StikDebug implementation is copied into our app.
enum StikDebugRequest {
    static func make(bundleID: String, pid: Int32) throws -> URL {
        guard !bundleID.isEmpty, pid > 0 else {
            throw NSError(domain: "StikDebugRequest", code: 1,
                          userInfo: [NSLocalizedDescriptionKey: "Missing current app identity"])
        }
        var route = URLComponents()
        route.scheme = "stikdebug"
        route.host = "enable-jit"
        route.queryItems = [URLQueryItem(name: "pid", value: String(pid)),
                            URLQueryItem(name: "bundle-id", value: bundleID),
                            URLQueryItem(name: "script-name", value: "universal.js")]
        guard let url = route.url else {
            throw NSError(domain: "StikDebugRequest", code: 2,
                          userInfo: [NSLocalizedDescriptionKey: "Could not create the JIT request"])
        }
        return url
    }
}
