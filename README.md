# EFPL Desktop IDE 🚀

**EFPL** is a powerful, lightweight, and modern scripting environment designed for simplicity and performance. This IDE provides a complete ecosystem for writing, testing, and visualizing EFPL scripts.

![EFPL Logo](assets/app_icon.ico)

## ✨ Features

- **🚀 Modern Editor**: Syntax-highlighted code editor with a clean, distraction-free interface.
- **📁 File Management**: Integrated file explorer to manage your `.efpl` scripts effortlessly.
- **📊 Built-in Visuals**: Native support for data visualization using `matplotlib` and `pandas`.
- **📚 Library System**: Easily toggle built-in libraries (Math, Array, Visual, etc.) to extend functionality.
- **🖥️ Integrated Console**: Real-time output and error tracking for debugging your scripts.
- **📦 Standalone Installer**: Professional Windows installer for easy distribution.

## 🛠️ Getting Started

### Installation

1. Download the latest `EFPL_IDE_Setup.exe` from the [releases](https://github.com/shanmugamani45/EFPL_VERSION_1/releases) page (if available) or the `installer_output` folder.
2. Run the installer and follow the on-screen instructions.
3. Launch **EFPL IDE** from your Start Menu or Desktop.

### Usage

1. **Create a Script**: Use the "New File" option or open an existing `.efpl` file from the workspace.
2. **Write Code**: Explore the `workspace/scripts` folder for examples like `data_demo.efpl` or `visual_charts.efpl`.
3. **Run**: Click the **Run** button to execute your script.
4. **Manage Libraries**: Use the **Libraries** menu to enable features like `visual` for charts.

## 📁 Project Structure

- `efpl_ui/`: GUI implementation using Tkinter.
- `efpl_core/`: Core interpreter and runtime logic.
- `efpl_runtime/`: Script execution engine and module management.
- `workspace/`: Your scripts, data files, and generated visuals.
- `assets/`: UI assets and branding.

## 🔧 Building from Source

If you want to build the executable yourself:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run with PyInstaller
pyinstaller --onedir --windowed --icon "assets/app_icon.ico" main.py
```
## Screen Shots
<img width="1917" height="1078" alt="image" src="https://github.com/user-attachments/assets/f4028e7c-8586-408f-8765-e07c3889367a" />

<img width="1918" height="1078" alt="image" src="https://github.com/user-attachments/assets/688125f8-7730-48dd-87f7-571421365ace" />

<img width="1917" height="1078" alt="image" src="https://github.com/user-attachments/assets/3e2c0ce6-fd63-4470-a317-2a54df09e05b" />

<img width="1918" height="1078" alt="image" src="https://github.com/user-attachments/assets/5adfb2b6-8785-41a0-9290-26d586bc1e53" />

<img width="1918" height="1078" alt="image" src="https://github.com/user-attachments/assets/e9ebb0b6-6c93-4b0f-a84b-bf75e20e7ab9" />


## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---
Created with ❤️ by [shanmugamani45](https://github.com/shanmugamani45)
