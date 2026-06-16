import tkinter as tk
from tkinter import ttk, messagebox, filedialog
# Monkeypatch platform.system to avoid WMI hang in TkinterDnD
import platform
platform.system = lambda: 'Windows'

from tkinterdnd2 import DND_FILES, TkinterDnD
import threading
import os
from src.backend import process_file
from src.converters.kordoc_converter import check_kordoc_dependency

class App(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("Doc/PDF to Markdown Converter (Korean Enhanced)")
        self.geometry("800x600")
        self.configure(bg="#FFF3E0") # Light Orange bg

        # Style
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TFrame", background="#FFF3E0")
        style.configure("TLabel", background="#FFF3E0", font=("Malgun Gothic", 10))
        style.configure("Header.TLabel", font=("Malgun Gothic", 16, "bold"), foreground="#E65100")
        style.configure("TButton", font=("Malgun Gothic", 10, "bold"), background="#FF9800", foreground="white")
        style.map("TButton", background=[("active", "#F57C00")])

        # Layout
        self.create_widgets()
        self.after(100, self.start_dependency_check)

    def create_widgets(self):
        # Header
        header = ttk.Label(self, text="📄 Doc/PDF to Markdown Converter", style="Header.TLabel")
        header.pack(pady=20)

        # Drop Zone
        self.drop_frame = tk.Frame(self, bg="#FFE0B2", bd=2, relief="groove")
        self.drop_frame.pack(fill="x", padx=40, pady=10, ipady=30)
        
        self.drop_label = tk.Label(
            self.drop_frame, 
            text="Drag & drop files here OR Click to select\n(이곳을 클릭하거나 파일을 드래그하세요)",
            bg="#FFE0B2", fg="#E65100",
            font=("Malgun Gothic", 12, "bold")
        )
        self.drop_label.pack(expand=True, fill="both")

        # Bind Drag events
        self.drop_label.drop_target_register(DND_FILES)
        self.drop_label.dnd_bind('<<Drop>>', self.on_drop)
        self.drop_frame.drop_target_register(DND_FILES)
        self.drop_frame.dnd_bind('<<Drop>>', self.on_drop)

        # Bind Click events for file dialog
        self.drop_label.bind("<Button-1>", self.open_files)
        self.drop_frame.bind("<Button-1>", self.open_files)
        self.drop_label.config(cursor="hand2")
        self.drop_frame.config(cursor="hand2")

        # File List (Progress)
        list_frame = ttk.Frame(self)
        list_frame.pack(fill="both", expand=True, padx=40, pady=10)
        
        ttk.Label(list_frame, text="Conversion Log:").pack(anchor="w")
        
        self.log_list = tk.Listbox(list_frame, font=("Consolas", 9), activestyle='none')
        self.log_list.pack(side="left", fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.log_list.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_list.config(yscrollcommand=scrollbar.set)

        # Status Bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = tk.Label(self, textvariable=self.status_var, relief="sunken", anchor="w", bg="#FFCC80")
        status_bar.pack(side="bottom", fill="x")

    def on_drop(self, event):
        files = self.split_files(event.data)
        if files:
            self.start_conversion(list(files))

    def open_files(self, event=None):
        files = filedialog.askopenfilenames(
            title="Select Files",
            filetypes=[
                ("All Supported", "*.docx *.doc *.hwp *.hwpx *.pdf *.pptx *.xlsx *.xls"),
                ("Word Files", "*.docx *.doc"),
                ("Hangul Files", "*.hwp *.hwpx"),
                ("PDF Files", "*.pdf"),
                ("PowerPoint Files", "*.pptx"),
                ("Excel Files", "*.xlsx *.xls"),
            ]
        )
        if files:
            self.start_conversion(list(files))

    def split_files(self, data):
        """
        TkinterDnD returns file paths as a curly-braced string if they contain spaces.
        Need robust parsing.
        """
        # Simple parser for Windows paths in TkinterDnD
        # Or usually it handles it, but let's be safe.
        # TkinterDnD often returns: {C:/path/a.pdf} C:/path/b.pdf
        if data.startswith('{') and data.endswith('}'):
            # This is a bit simplistic, properly splitting requires regex for multiple braced items
            # But for single file drop which is most common or standard space separation...
            # Let's clean braces widely for now if users drop simple lists.
            # A better way is relying on the widget.tk.splitlist(data)
            try:
                return self.tk.splitlist(data)
            except:
                return [data.strip('{}')]
        else:
             # Space separated?
             return self.tk.splitlist(data)

    def log(self, message):
        self.log_list.insert(tk.END, message)
        self.log_list.see(tk.END)

    def start_dependency_check(self):
        threading.Thread(target=self.check_dependencies_thread, daemon=True).start()

    def check_dependencies_thread(self):
        status = check_kordoc_dependency()
        self.after(0, self.show_kordoc_status, status)

    def show_kordoc_status(self, status):
        if status["available"]:
            detail = status["version"] or os.path.basename(status["path"])
            self.log(f"[CHECK] kordoc OK: {detail}")
            if status["warning"]:
                self.log(f"[WARN] {status['warning']}")
            return

        self.log(f"[WARN] {status['warning']}")
        self.log(f"[HINT] Install optional kordoc CLI: {status['install_hint']}")
        self.status_var.set("Ready - optional kordoc CLI not found")

    def start_conversion(self, files):
        self.status_var.set("Converting...")
        threading.Thread(target=self.process_files_thread, args=(files,), daemon=True).start()

    def process_files_thread(self, files):
        # Tkinter is not thread-safe: all widget access from this worker
        # thread must be marshalled to the main loop via self.after().
        for file in files:
            if not os.path.isfile(file):
                continue

            self.after(0, self.log, f"Processing: {os.path.basename(file)}...")
            success, msg = process_file(file)
            status = "SUCCESS" if success else "FAILED"
            self.after(0, self.log, f"[{status}] {msg}")

        def finish():
            self.status_var.set("Finished.")
            messagebox.showinfo("Done", "All files processed!")
        self.after(0, finish)

if __name__ == "__main__":
    app = App()
    app.mainloop()
