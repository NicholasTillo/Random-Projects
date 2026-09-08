"""Turn an image into a pixel-art version. Pillow does the work, tkinter drives it."""
import tkinter as tk
from tkinter import filedialog, ttk

from PIL import Image, ImageTk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:                      # drag-and-drop off, Open button still works
    DND_FILES = TkinterDnD = None

PREVIEW = 560


def pixelate(img, block, colors):
    """Low-res version of img: blocks of `block` px averaged, palette cut to `colors`.

    Returns the small image; the caller upscales it with NEAREST for crisp squares.
    """
    w, h = img.size
    small = img.resize((max(1, w // block), max(1, h // block)), Image.BOX)
    if colors < 256:
        small = small.quantize(colors=colors, dither=Image.Dither.NONE).convert("RGB")
    return small


class App:
    def __init__(self, root):
        self.src = None          # original PIL image
        self.crop = None         # (l, t, r, b) in source coords
        self.scale = 1.0         # preview px per source px
        self.drag = None
        self.photo = None        # keep a ref or tkinter drops the image

        bar = ttk.Frame(root, padding=6)
        bar.pack(fill="x")
        ttk.Button(bar, text="Open", command=self.open).pack(side="left")
        ttk.Button(bar, text="Save", command=self.save).pack(side="left", padx=4)
        ttk.Button(bar, text="Reset crop", command=self.reset_crop).pack(side="left")

        self.block = tk.IntVar(value=8)
        self.colors = tk.IntVar(value=32)
        for label, var, lo, hi in (("Pixel size", self.block, 1, 64),
                                   ("Colors", self.colors, 2, 256)):
            row = ttk.Frame(root, padding=(6, 0))
            row.pack(fill="x")
            ttk.Label(row, text=label, width=10).pack(side="left")
            ttk.Label(row, textvariable=var, width=4).pack(side="right")
            ttk.Scale(row, from_=lo, to=hi, variable=var,
                      command=lambda _v, v=var: (v.set(int(float(_v))), self.render())
                      ).pack(side="left", fill="x", expand=True)

        self.canvas = tk.Canvas(root, width=PREVIEW, height=PREVIEW,
                                bg="#222", highlightthickness=0)
        self.canvas.pack(padx=6, pady=6)
        self.canvas.bind("<ButtonPress-1>", self.press)
        self.canvas.bind("<B1-Motion>", self.motion)
        self.canvas.bind("<ButtonRelease-1>", self.release)
        if DND_FILES and hasattr(root, "drop_target_register"):
            root.drop_target_register(DND_FILES)
            root.dnd_bind("<<Drop>>", self.dropped)

        hint = "Drop an image here or click Open." if DND_FILES else "Open an image to start."
        self.status = ttk.Label(root, text=hint, padding=(6, 0, 6, 6))
        self.status.pack(fill="x")

    # --- pipeline -----------------------------------------------------------
    def base(self):
        return self.src.crop(self.crop) if self.crop else self.src

    def open(self):
        path = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"), ("All", "*.*")])
        if path:
            self.load(path)

    def dropped(self, event):
        paths = self.canvas.tk.splitlist(event.data)   # {braced} when the path has spaces
        if paths:
            self.load(paths[0])

    def load(self, path):
        try:
            self.src = Image.open(path).convert("RGB")
        except (OSError, ValueError) as e:
            self.status.config(text=f"Can't open {path}: {e}")
            return
        self.crop = None
        self.render()

    def save(self):
        if not self.src:
            return
        path = filedialog.asksaveasfilename(defaultextension=".png",
                                            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg")])
        if not path:
            return
        base = self.base()
        small = pixelate(base, self.block.get(), self.colors.get())
        small.resize(base.size, Image.NEAREST).save(path)
        self.status.config(text=f"Saved {path}")

    def render(self):
        if not self.src:
            return
        base = self.base()
        small = pixelate(base, self.block.get(), self.colors.get())
        self.scale = min(PREVIEW / base.width, PREVIEW / base.height)
        shown = small.resize((max(1, round(base.width * self.scale)),
                              max(1, round(base.height * self.scale))), Image.NEAREST)
        self.photo = ImageTk.PhotoImage(shown)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
        self.status.config(text=f"{base.width}x{base.height} source -> "
                                f"{small.width}x{small.height} pixels, {self.colors.get()} colors. "
                                f"Drag on the image to crop.")

    # --- crop ---------------------------------------------------------------
    def reset_crop(self):
        self.crop = None
        self.render()

    def press(self, e):
        self.drag = (e.x, e.y)

    def motion(self, e):
        if not self.drag:
            return
        self.canvas.delete("sel")
        self.canvas.create_rectangle(*self.drag, e.x, e.y, outline="#0f0", tags="sel")

    def release(self, e):
        if not self.src or not self.drag:
            return
        x0, y0 = self.drag
        self.drag = None
        l, t = min(x0, e.x) / self.scale, min(y0, e.y) / self.scale
        r, b = max(x0, e.x) / self.scale, max(y0, e.y) / self.scale
        if r - l < 2 or b - t < 2:          # a click, not a drag
            return self.canvas.delete("sel")
        ox, oy = (self.crop[0], self.crop[1]) if self.crop else (0, 0)
        base = self.base()
        self.crop = (ox + int(l), oy + int(t),
                     ox + int(min(r, base.width)), oy + int(min(b, base.height)))
        self.render()


if __name__ == "__main__":
    root = TkinterDnD.Tk() if TkinterDnD else tk.Tk()
    root.title("Image Pixelier")
    App(root)
    root.mainloop()
