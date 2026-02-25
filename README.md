# Grynk Programming Language

**Powerful. Fast. Alive.**

Grynk is a modern, fast, and highly expressive scripting language built for web APIs, AI, automation, and real-time internet tasks. It feels fast like Rust and readable like Python, with absolutely zero unnecessary symbols.

---

## 🚀 Installation

It is highly recommended to install Grynk using the official Windows Installer. 

The installer will automatically set up the CLI tool and seamlessly install the **VS Code Extension** so you get the Grynk icon and syntax highlighting immediately.

1. Go to the [Releases](../../releases) page.
2. Download **`Grynk_Windows_Installer.exe`**.
3. Run the installer and click Next.
4. **Done!** Open any terminal and run your code.

### Linux & macOS

You have two ways to install Grynk on Linux:

#### Option 1: Standalone Binary (Easiest)
1. Go to the [Releases](../../releases) page and download the `grynk` file (the one without an extension).
2. Open your terminal and make the file executable:
   ```bash
   chmod +x grynk
   ```
3. Move it to your local bin folder to run it from anywhere:
   ```bash
   sudo mv grynk /usr/local/bin/
   ```

#### Option 2: Install from Source
If you have Python 3 installed and want to run Grynk natively:
1. Clone this repository to your machine.
2. Run the provided setup script:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```
   *This script automatically installs dependencies and creates a global `grynk` command for you.*

---

## 🌤️ Showcase: Weather App
Grynk comes with a live terminal weather app!
```bash
grynk examples/weather.grk
```

---

## ⚡ Quick Start

Create a new file called `app.grk`:
```grynk
# Run a quick AI prompt and fetch from the web!
gx.banner("GRYNK APP", "cyan")

let joke = gx.get("https://official-joke-api.appspot.com/random_joke").json
say "Here is a joke: {joke.get('setup')} - {joke.get('punchline')}"
```

Run it via your terminal:
```bash
grynk run app.grk
```

---

## 🛠️ CLI Commands

Grynk comes with a powerful CLI out of the box.

| Command | Description |
| :--- | :--- |
| `grynk run <file>` | Runs a `.grk` script |
| `grynk <file>` | Runs a script directly |
| `grynk repl` | Starts the interactive multi-line REPL shell |
| `grynk new <name>` | Scaffolds a new boilerplate Grynk project |
| `grynk help` | Shows the full language syntax and built-in reference |

---

## 📖 Language Syntax Overview

### Variables & Functions
```grynk
let immutable_name = "Grynk"
mut speed = 100
speed += 50

fn calculate(a, b) {
    return a ** b
}
say calculate(2, 10)  # Prints 1024
```

### Control Flow
```grynk
let x = 10
if x > 50 {
    say "Huge"
} elif x > 5 {
    say "Medium"
} else {
    say "Small"
}

loop 3 times {
    say "Repeating!"
}

let items = [1, 2, 3]
for item in items {
    say item
}
```

### Data Pipelines
The `|>` pipe operator allows you to chain commands smoothly:
```grynk
[3, 1, 4, 1, 5, 9] 
    |> gx.sort() 
    |> gx.unique() 
    |> say
# Prints: [1, 3, 4, 5, 9]
```

### The Omnipotent `gx` Object
Grynk requires **zero imports ever**. Every powerful tool you need is built directly into the global `gx` object. 

- **Web:** `gx.get()`, `gx.post()`, `gx.scrape()`
- **AI:** `gx.ai()`, `gx.ai_summarize()`, `gx.ai_code()`
- **Crypto:** `gx.uuid()`, `gx.hash()`, `gx.sha256()`
- **Files:** `gx.read()`, `gx.write()`, `gx.read_json()`
- **Time:** `gx.now()`, `gx.sleep()`, `gx.bench()`
- **Math/Data:** `gx.clamp()`, `gx.sort()`, `gx.map()`, `gx.filter()`
- **Terminal:** `gx.color()`, `gx.banner()`, `gx.table()`, `gx.clear()`
- **System:** `gx.run()`, `gx.env()`, `gx.platform()`

*(Type `grynk help` in your terminal to see the complete list!)*

---

## 🖼️ Graphical UI (GxGUI)

Grynk includes a premium, built-in GUI engine that makes creating desktop applications incredibly simple. It uses **CustomTkinter** for a modern, sleek look by default.

```grynk
# A simple "Counter" app in 10 lines
let win = gx.window("Grynk App", 400, 300)
let lbl = gx.label("Welcome to Grynk!")
let count = 0

fn on_click() {
    mut count = count + 1
    lbl.set("Clicked {count} times!")
}

gx.button("Click Me!", on_click)
gx.gui_run()
```

### GUI Reference

| Method | Description |
| :--- | :--- |
| `gx.window(title, w, h)` | Creates a new application window |
| `gx.label(text)` | Adds a text label to the window |
| `gx.button(text, fn)` | Adds a button that runs a function when clicked |
| `gx.entry(placeholder)` | Adds a text input field |
| `gx.gui_run()` | Starts the application event loop |

---

## 🧱 Building from Source

If you want to build the `grynk.exe` compiler from source:

1. Clone this repository.
2. Ensure you have Python installed.
3. Run `python build.py`.
4. The standalone binary will be generated in `/dist/grynk.exe`.

To build the installer, you need Inno Setup to compile `installer.iss`.
