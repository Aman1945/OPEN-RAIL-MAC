// Open Rails for macOS: the menu as a real Mac app.
//
// A native window (the same size as the Open Rails menu on Windows) that shows the menu page with WebKit.
// The menu itself is orts-menu.py, a small local server that this app starts and stops.
// Run with --selftest to load the page without showing a window and print what it contains.

import Cocoa
import WebKit

final class AppDelegate: NSObject, NSApplicationDelegate, WKUIDelegate, WKNavigationDelegate {
    var window: NSWindow!
    var web: WKWebView!
    var server: Process?
    var output = ""
    var loaded = false
    var quitting = false
    let selfTest = CommandLine.arguments.contains("--selftest")

    func applicationDidFinishLaunching(_ notification: Notification) {
        if selfTest { NSApp.setActivationPolicy(.accessory) }
        buildMenu()
        buildWindow()
        guard let programDir = locateProgramDir() else { NSApp.terminate(nil); return }
        startServer(programDir: programDir)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    func applicationWillTerminate(_ notification: Notification) {
        quitting = true
        server?.terminate()   // the game runs on its own and keeps going
    }

    // MARK: window and menu bar

    func buildWindow() {
        web = WKWebView(frame: NSRect(x: 0, y: 0, width: 854, height: 548), configuration: WKWebViewConfiguration())
        web.uiDelegate = self
        web.navigationDelegate = self
        window = NSWindow(contentRect: web.frame, styleMask: [.titled, .closable, .miniaturizable], backing: .buffered, defer: false)
        window.title = "Open Rails"
        window.contentView = web
        window.backgroundColor = NSColor(srgbRed: 240 / 255, green: 240 / 255, blue: 240 / 255, alpha: 1)
        window.isReleasedWhenClosed = false
        window.center()
        if !selfTest {
            window.makeKeyAndOrderFront(nil)
            NSApp.activate(ignoringOtherApps: true)
        }
    }

    func buildMenu() {
        let main = NSMenu()
        NSApp.mainMenu = main

        let appItem = NSMenuItem(); main.addItem(appItem)
        let app = NSMenu(); appItem.submenu = app
        app.addItem(withTitle: "About Open Rails", action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
        app.addItem(.separator())
        app.addItem(withTitle: "Hide Open Rails", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        app.addItem(.separator())
        app.addItem(withTitle: "Quit Open Rails", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")

        let editItem = NSMenuItem(); main.addItem(editItem)
        let edit = NSMenu(title: "Edit"); editItem.submenu = edit
        edit.addItem(withTitle: "Cut", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        edit.addItem(withTitle: "Copy", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        edit.addItem(withTitle: "Paste", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        edit.addItem(withTitle: "Select All", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")

        let windowItem = NSMenuItem(); main.addItem(windowItem)
        let win = NSMenu(title: "Window"); windowItem.submenu = win
        win.addItem(withTitle: "Minimize", action: #selector(NSWindow.performMiniaturize(_:)), keyEquivalent: "m")
        win.addItem(withTitle: "Close", action: #selector(NSWindow.performClose(_:)), keyEquivalent: "w")
        NSApp.windowsMenu = win
    }

    // MARK: finding the game and starting the menu server

    func isProgramDir(_ url: URL) -> Bool {
        FileManager.default.fileExists(atPath: url.appendingPathComponent("RunActivity.dll").path)
    }

    /// The Program folder: next to this app, from the environment, or one the user chose before.
    func locateProgramDir() -> URL? {
        var candidates: [URL] = []
        if let env = ProcessInfo.processInfo.environment["ORTS_PROGRAM_DIR"] { candidates.append(URL(fileURLWithPath: env)) }
        candidates.append(Bundle.main.bundleURL.deletingLastPathComponent().appendingPathComponent("Program"))
        if let saved = UserDefaults.standard.string(forKey: "programDir") { candidates.append(URL(fileURLWithPath: saved)) }
        if let hit = candidates.first(where: isProgramDir) { return hit }

        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.prompt = "Choose"
        panel.message = "Choose the Open Rails folder you unzipped. It contains a folder called Program."
        while panel.runModal() == .OK {
            guard let url = panel.url else { break }
            for candidate in [url, url.appendingPathComponent("Program")] where isProgramDir(candidate) {
                UserDefaults.standard.set(candidate.path, forKey: "programDir")
                return candidate
            }
            let alert = NSAlert()
            alert.messageText = "That folder does not contain Open Rails."
            alert.informativeText = "Choose the folder that contains the folder called Program."
            alert.runModal()
        }
        return nil
    }

    func startServer(programDir: URL) {
        let pythons = ["/usr/bin/python3", "/opt/homebrew/bin/python3", "/usr/local/bin/python3"]
        guard let python = pythons.first(where: { FileManager.default.isExecutableFile(atPath: $0) }),
              let script = Bundle.main.url(forResource: "orts-menu", withExtension: "py") else {
            fail("Python 3 was not found.\n\nInstall the Xcode Command Line Tools by running this in Terminal:\n\nxcode-select --install")
            return
        }
        let p = Process()
        p.executableURL = URL(fileURLWithPath: python)
        p.arguments = [script.path]
        var env = ProcessInfo.processInfo.environment
        env["ORTS_NO_BROWSER"] = "1"
        env["PYTHONUNBUFFERED"] = "1"
        env["ORTS_PROGRAM_DIR"] = programDir.path
        env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + (env["PATH"] ?? "/usr/bin:/bin")
        p.environment = env
        let pipe = Pipe()
        p.standardOutput = pipe
        p.standardError = pipe
        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            if data.isEmpty { return }
            DispatchQueue.main.async { self?.gotOutput(String(decoding: data, as: UTF8.self)) }
        }
        p.terminationHandler = { [weak self] _ in
            DispatchQueue.main.async {
                guard let self = self, !self.quitting else { return }
                self.fail("The Open Rails menu stopped.\n\n" + String(self.output.suffix(800)))
            }
        }
        do { try p.run() } catch { fail("Could not start the menu: \(error.localizedDescription)"); return }
        server = p
    }

    func gotOutput(_ text: String) {
        output += text
        if !loaded, let range = output.range(of: "http://127.0.0.1:[0-9]+/", options: .regularExpression),
           let url = URL(string: String(output[range]) + "?app=1") {
            loaded = true
            web.load(URLRequest(url: url))
        }
    }

    func fail(_ message: String) {
        let alert = NSAlert()
        alert.messageText = "Open Rails"
        alert.informativeText = message
        alert.alertStyle = .warning
        alert.runModal()
        NSApp.terminate(nil)
    }

    // MARK: web view

    /// Links to other sites (the manual, the Open Rails website) open in the browser, not in this window.
    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if let url = navigationAction.request.url, url.scheme?.hasPrefix("http") == true, url.host != "127.0.0.1" {
            NSWorkspace.shared.open(url)
            decisionHandler(.cancel)
            return
        }
        decisionHandler(.allow)
    }

    /// window.open() from the page: open in the browser.
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                 for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = navigationAction.request.url { NSWorkspace.shared.open(url) }
        return nil
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        guard selfTest else { return }
        let js = """
        JSON.stringify({title: document.title, native: document.documentElement.classList.contains('native'),
          fakeTitleBar: getComputedStyle(document.getElementById('title')).display, width: innerWidth, height: innerHeight,
          profiles: document.getElementById('profile').options.length, routes: document.getElementById('route').options.length,
          setup: document.getElementById('details').innerText.slice(0, 200)})
        """
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {   // let the page load its data first
            self.web.evaluateJavaScript(js) { result, error in
                print("SELFTEST " + ((result as? String) ?? "error: \(String(describing: error))"))
                fflush(stdout)
                NSApp.terminate(nil)
            }
        }
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
