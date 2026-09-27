"""Run the native dialog in its own process: Tk must own its UI thread."""
import json
import tkinter as tk
from tkinter import filedialog


def main():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    try:
        folder = filedialog.askdirectory(parent=root, title='Escolha a pasta para salvar os downloads', mustexist=True)
        print(json.dumps({'destination': folder or None}))
    finally:
        root.destroy()


if __name__ == '__main__':
    main()
