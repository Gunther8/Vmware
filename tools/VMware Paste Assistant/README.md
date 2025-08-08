# VMware Paste Assistant (AutoHotkey Script)

A lightweight Windows tool that simulates typing clipboard commands into VMware console windows, especially when copy-paste is not supported in vSphere Web Client.

🌐 适用于 VMware 控制台无法粘贴命令的场景，通过模拟键盘逐字输入，解决“手动输入效率太低”的问题。

## ✨ Features | 功能

- 🖱️ Press `Ctrl + Shift + V` to simulate typing clipboard contents
- ⌨️ Types one character at a time with delay to avoid input loss
- ⏎ Auto-press Enter after each line
- 🖥️ Visible system tray icon with right-click to exit
- ✅ No need to install VMware Tools or open SSH
- 🔒 No auto-start, runs only when you need it



## 🚀 Usage | 使用方法

1. 📋 Copy the commands you want to send
2. 🖱️ Focus your VMware virtual machine console window
3. 🎯 Press `Ctrl + Shift + V` — script will start simulating input
4. 🛑 Right-click tray icon to exit the script

## 📦 Download | 下载

- ✅ [Click here to download paste.exe](https://github.com/Gunther8/Vmware/blob/main/tools/VMware%20Paste%20Assistant/paste-1.exe)
- 💡 You can also download and compile the `.ahk` script manually with AutoHotkey

## 🔧 Build Your Own

If you want to modify or recompile:

```bash
# Download AutoHotkey (https://www.autohotkey.com/)
# Then right-click paste.ahk → Compile Script

