from __future__ import annotations

import ast
import sys
import tkinter as tk
from dataclasses import dataclass
from decimal import Decimal, DivisionByZero, InvalidOperation, getcontext
from pathlib import Path
from tkinter import messagebox

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps, ImageTk


getcontext().prec = 28

APP_TITLE = "Calcolatrice Sexy"
WINDOW_SIZE = (980, 620)
ASSET_PATH = Path(__file__).resolve().parent / "risorse" / "trait.png"

OPERATORS = {"+", "-", "*", "/"}
DISPLAY_OPERATORS = {"*": "x", "/": "÷"}


def blend_rgb(color: tuple[int, int, int], target: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    return tuple(int(color[index] + (target[index] - color[index]) * amount) for index in range(3))


def clamp_decimal_text(text: str, limit: int = 18) -> str:
    if len(text) <= limit:
        return text
    try:
        number = Decimal(text)
    except InvalidOperation:
        return text[:limit]
    return f"{number:.10E}".replace("E+", "e+").replace("E-", "e-")


def format_decimal(value: Decimal) -> str:
    if not value.is_finite():
        raise ValueError("Numero non valido")
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in {"", "-0"}:
        text = "0"
    return clamp_decimal_text(text)


def prettify_expression(tokens: list[str]) -> str:
    pretty_tokens: list[str] = []
    for token in tokens:
        pretty_tokens.append(DISPLAY_OPERATORS.get(token, token))
    return " ".join(pretty_tokens)


@dataclass
class DisplayState:
    header: str
    result: str


class CalculatorEngine:
    def __init__(self) -> None:
        self.tokens: list[str] = []
        self.history = ""
        self.error_text = ""
        self.just_evaluated = False

    def clear(self) -> DisplayState:
        self.tokens = []
        self.history = ""
        self.error_text = ""
        self.just_evaluated = False
        return self.display_state()

    def press(self, key: str) -> DisplayState:
        if key == "AC":
            return self.clear()

        if self.error_text:
            self.clear()

        if key in "0123456789":
            self._append_digit(key)
        elif key == ".":
            self._append_decimal_point()
        elif key in OPERATORS:
            self._append_operator(key)
        elif key == "=":
            self._evaluate_current()
        elif key == "DEL":
            self._backspace()
        elif key == "%":
            self._percent()
        elif key == "+/-":
            self._toggle_sign()
        return self.display_state()

    def display_state(self) -> DisplayState:
        if self.error_text:
            return DisplayState("Premi AC per ripartire", self.error_text)

        header = self.history or prettify_expression(self.tokens) or "trait baciamoci amore...... (STO SCHERZANDO)"
        result = self._preview_result()
        return DisplayState(header, result)

    def _append_digit(self, digit: str) -> None:
        if self.just_evaluated:
            self.tokens = []
            self.history = ""
            self.just_evaluated = False

        if not self.tokens or self._is_operator(self.tokens[-1]):
            self.tokens.append(digit)
            return

        current = self.tokens[-1]
        negative = current.startswith("-")
        core = current[1:] if negative else current

        if core in {"0", ""} and "." not in core:
            core = digit if digit != "0" else "0"
        else:
            core += digit

        self.tokens[-1] = f"-{core}" if negative else core

    def _append_decimal_point(self) -> None:
        if self.just_evaluated:
            self.tokens = []
            self.history = ""
            self.just_evaluated = False

        if not self.tokens or self._is_operator(self.tokens[-1]):
            self.tokens.append("0.")
            return

        current = self.tokens[-1]
        if "." not in current:
            self.tokens[-1] = f"{current}."

    def _append_operator(self, operator: str) -> None:
        if not self.tokens:
            if operator == "-":
                self.tokens.append("-0")
            return

        self.history = ""
        self.just_evaluated = False

        if self._is_operator(self.tokens[-1]):
            self.tokens[-1] = operator
            return

        self.tokens.append(operator)

    def _backspace(self) -> None:
        self.history = ""
        self.just_evaluated = False

        if not self.tokens:
            return

        current = self.tokens[-1]
        if self._is_operator(current):
            self.tokens.pop()
            return

        shortened = current[:-1]
        if shortened in {"", "-"}:
            self.tokens.pop()
            return

        self.tokens[-1] = shortened

    def _percent(self) -> None:
        if not self.tokens or self._is_operator(self.tokens[-1]):
            return

        self.history = ""
        self.just_evaluated = False

        try:
            number = Decimal(self.tokens[-1]) / Decimal("100")
        except InvalidOperation:
            return
        self.tokens[-1] = format_decimal(number)

    def _toggle_sign(self) -> None:
        self.history = ""
        self.just_evaluated = False

        if not self.tokens:
            self.tokens.append("-0")
            return

        if self._is_operator(self.tokens[-1]):
            self.tokens.append("-0")
            return

        current = self.tokens[-1]
        if current.startswith("-"):
            stripped = current[1:] or "0"
            self.tokens[-1] = stripped
        else:
            self.tokens[-1] = f"-{current}"

    def _evaluate_current(self) -> None:
        working_tokens = self._tokens_without_trailing_operator()
        if not working_tokens:
            return

        expression_text = prettify_expression(working_tokens)
        try:
            result = self._evaluate_tokens(working_tokens)
        except ZeroDivisionError:
            self._set_error("Impossibile dividere per zero")
            return
        except (SyntaxError, ValueError, InvalidOperation, DivisionByZero):
            self._set_error("Operazione non valida")
            return

        self.tokens = [result]
        self.history = f"{expression_text} ="
        self.just_evaluated = True

    def _preview_result(self) -> str:
        working_tokens = self._tokens_without_trailing_operator()
        if not working_tokens:
            return "0"

        try:
            return self._evaluate_tokens(working_tokens)
        except ZeroDivisionError:
            return "Errore"
        except (SyntaxError, ValueError, InvalidOperation, DivisionByZero):
            current = working_tokens[-1]
            return clamp_decimal_text(current.replace("+", "")) if not self._is_operator(current) else "0"

    def _tokens_without_trailing_operator(self) -> list[str]:
        if self.tokens and self._is_operator(self.tokens[-1]):
            return self.tokens[:-1]
        return list(self.tokens)

    def _set_error(self, message: str) -> None:
        self.tokens = []
        self.history = ""
        self.error_text = message
        self.just_evaluated = False

    @staticmethod
    def _is_operator(token: str) -> bool:
        return token in OPERATORS

    def _evaluate_tokens(self, tokens: list[str]) -> str:
        expression = "".join(tokens)
        tree = ast.parse(expression, mode="eval")
        value = self._eval_ast(tree.body)
        return format_decimal(value)

    def _eval_ast(self, node: ast.AST) -> Decimal:
        if isinstance(node, ast.BinOp):
            left = self._eval_ast(node.left)
            right = self._eval_ast(node.right)

            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                if right == 0:
                    raise ZeroDivisionError
                return left / right
            raise ValueError("Operatore non consentito")

        if isinstance(node, ast.UnaryOp):
            operand = self._eval_ast(node.operand)
            if isinstance(node.op, ast.UAdd):
                return operand
            if isinstance(node.op, ast.USub):
                return -operand
            raise ValueError("Segno non consentito")

        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return Decimal(str(node.value))

        if hasattr(ast, "Num") and isinstance(node, ast.Num):
            return Decimal(str(node.n))

        raise ValueError("Espressione non supportata")


class CalculatorApp:
    PANEL_BG = "#161c27"
    PANEL_EDGE = (255, 255, 255, 52)
    PALETTE = {
        "digit": {"fill": (35, 43, 57), "text": "#f5f7fb"},
        "function": {"fill": (52, 63, 82), "text": "#f5f7fb"},
        "operator": {"fill": (255, 143, 104), "text": "#10131a"},
        "equal": {"fill": (255, 191, 94), "text": "#10131a"},
    }

    def __init__(self, root: tk.Tk) -> None:
        if not ASSET_PATH.exists():
            raise FileNotFoundError(f"Immagine non trovata: {ASSET_PATH}")

        self.root = root
        self.root.title(APP_TITLE)
        self.root.configure(bg="#0a0d12")
        self.root.resizable(False, False)

        self.engine = CalculatorEngine()
        self.button_assets: dict[tuple[str, int, int], dict[str, ImageTk.PhotoImage]] = {}
        self.button_bg = self.PANEL_BG

        self._center_window(*WINDOW_SIZE)
        self._build_scene()
        self._build_widgets()
        self._bind_keyboard()
        self._refresh_display()

    def _center_window(self, width: int, height: int) -> None:
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x_pos = max((screen_w - width) // 2, 0)
        y_pos = max((screen_h - height) // 2, 0)
        self.root.geometry(f"{width}x{height}+{x_pos}+{y_pos}")

    def _build_scene(self) -> None:
        width, height = WINDOW_SIZE
        self.canvas = tk.Canvas(
            self.root,
            width=width,
            height=height,
            highlightthickness=0,
            bd=0,
            bg="#0b0e14",
        )
        self.canvas.pack(fill="both", expand=True)

        source = Image.open(ASSET_PATH).convert("RGB")
        self.background_photo = ImageTk.PhotoImage(self._create_background(source, (width, height)))
        self.left_card_photo = ImageTk.PhotoImage(self._create_photo_card(source, (412, 338)))
        self.panel_photo = ImageTk.PhotoImage(self._create_panel_art((430, 560)))

        self.canvas.create_image(0, 0, anchor="nw", image=self.background_photo)
        self.canvas.create_image(44, 68, anchor="nw", image=self.left_card_photo)
        self.canvas.create_image(506, 30, anchor="nw", image=self.panel_photo)

        self.canvas.create_text(
            64,
            438,
            anchor="nw",
            text="CALCOLATRICE SEXY",
            fill="#f8f4ef",
            font=("Bahnschrift SemiBold", 27),
        )
        self.canvas.create_text(
            64,
            478,
            anchor="nw",
            text="trait se vedi questo sei GAY",
            fill="#e1d6cc",
            font=("Segoe UI", 12),
        )
   

    def _build_widgets(self) -> None:
        self.panel_content = tk.Frame(self.canvas, bg=self.PANEL_BG)
        self.canvas.create_window(536, 54, anchor="nw", window=self.panel_content, width=372, height=512)

        self.panel_content.grid_columnconfigure(0, weight=1)

        self.topline = tk.Label(
            self.panel_content,
            text="TRAIT MODE",
            fg="#ffbb8c",
            bg=self.PANEL_BG,
            font=("Segoe UI Semibold", 10),
            anchor="w",
            padx=2,
        )
        self.topline.grid(row=0, column=0, sticky="ew", pady=(4, 12))

        self.header_var = tk.StringVar()
        self.result_var = tk.StringVar()

        self.header_label = tk.Label(
            self.panel_content,
            textvariable=self.header_var,
            fg="#b5bfd3",
            bg=self.PANEL_BG,
            font=("Segoe UI", 12),
            justify="right",
            anchor="e",
            padx=4,
        )
        self.header_label.grid(row=1, column=0, sticky="ew")

        self.result_label = tk.Label(
            self.panel_content,
            textvariable=self.result_var,
            fg="#f9fbff",
            bg=self.PANEL_BG,
            font=("Bahnschrift SemiBold", 34),
            justify="right",
            anchor="e",
            padx=2,
            pady=12,
        )
        self.result_label.grid(row=2, column=0, sticky="ew", pady=(2, 18))

        divider = tk.Frame(self.panel_content, height=1, bg="#283040")
        divider.grid(row=3, column=0, sticky="ew", pady=(0, 18))

        self.buttons_frame = tk.Frame(self.panel_content, bg=self.PANEL_BG)
        self.buttons_frame.grid(row=4, column=0, sticky="nsew")
        self.panel_content.grid_rowconfigure(4, weight=1)

        for column in range(4):
            self.buttons_frame.grid_columnconfigure(column, weight=1, uniform="buttons")
        for row in range(5):
            self.buttons_frame.grid_rowconfigure(row, weight=1, uniform="buttons")

        layout = [
            [("AC", "function", 1), ("DEL", "function", 1), ("%", "function", 1), ("÷", "operator", 1)],
            [("7", "digit", 1), ("8", "digit", 1), ("9", "digit", 1), ("x", "operator", 1)],
            [("4", "digit", 1), ("5", "digit", 1), ("6", "digit", 1), ("-", "operator", 1)],
            [("1", "digit", 1), ("2", "digit", 1), ("3", "digit", 1), ("+", "operator", 1)],
            [("+/-", "function", 1), ("0", "digit", 1), (".", "digit", 1), ("=", "equal", 1)], # sono disoccupato btw
        ]

        for row_index, row in enumerate(layout):
            for column_index, (label, role, span) in enumerate(row):
                internal_value = {"x": "*", "÷": "/"}.get(label, label)
                button = self._make_button(
                    self.buttons_frame,
                    label=label,
                    role=role,
                    width=86,
                    height=68,
                    command=lambda value=internal_value: self._on_press(value),
                )
                button.grid(
                    row=row_index,
                    column=column_index,
                    columnspan=span,
                    sticky="nsew",
                    padx=6,
                    pady=6,
                )

    def _bind_keyboard(self) -> None:
        self.root.bind("<Key>", self._handle_keypress)

    def _handle_keypress(self, event: tk.Event) -> None:
        key = event.keysym
        char = event.char

        if char in "0123456789":
            self._on_press(char)
            return
        if char in {"+", "-", "*", "/", "%", "="}:
            self._on_press(char)
            return
        if char in {".", ","}:
            self._on_press(".")
            return
        if char in {"x", "X"}:
            self._on_press("*")
            return

        special_map = {
            "Return": "=",
            "KP_Enter": "=",
            "BackSpace": "DEL",
            "Delete": "AC",
            "Escape": "AC",
        }
        mapped = special_map.get(key)
        if mapped:
            self._on_press(mapped)

    def _on_press(self, value: str) -> None:
        self.engine.press(value)
        self._refresh_display()

    def _refresh_display(self) -> None:
        state = self.engine.display_state()
        self.header_var.set(clamp_decimal_text(state.header, 38))
        self.result_var.set(clamp_decimal_text(state.result, 20))

    def _make_button(
        self,
        parent: tk.Frame,
        label: str,
        role: str,
        width: int,
        height: int,
        command,
    ) -> tk.Button:
        assets = self._get_button_assets(role, width, height)
        text_color = self.PALETTE[role]["text"]

        button = tk.Button(
            parent,
            image=assets["normal"],
            text=label,
            compound="center",
            font=("Segoe UI Semibold", 16),
            fg=text_color,
            bg=self.button_bg,
            activebackground=self.button_bg,
            activeforeground=text_color,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            cursor="hand2",
            command=command,
            padx=0,
            pady=0,
            takefocus=False,
        )
        button._images = assets  
        button.bind("<Enter>", lambda _event, widget=button: widget.config(image=widget._images["hover"]))  
        button.bind("<Leave>", lambda _event, widget=button: widget.config(image=widget._images["normal"]))  
        button.bind("<ButtonPress-1>", lambda _event, widget=button: widget.config(image=widget._images["pressed"])) 
        button.bind("<ButtonRelease-1>", lambda _event, widget=button: widget.config(image=widget._images["hover"]))  
        return button

    def _get_button_assets(self, role: str, width: int, height: int) -> dict[str, ImageTk.PhotoImage]:
        cache_key = (role, width, height)
        if cache_key not in self.button_assets:
            fill_rgb = self.PALETTE[role]["fill"]
            self.button_assets[cache_key] = {
                "normal": ImageTk.PhotoImage(self._create_button_art((width, height), fill_rgb, 0.0, 0)),
                "hover": ImageTk.PhotoImage(self._create_button_art((width, height), fill_rgb, 0.1, 0)),
                "pressed": ImageTk.PhotoImage(self._create_button_art((width, height), fill_rgb, -0.06, 2)),
            }
        return self.button_assets[cache_key]

    def _create_background(self, source: Image.Image, size: tuple[int, int]) -> Image.Image:
        base = ImageOps.fit(source, size, method=Image.Resampling.LANCZOS, centering=(0.45, 0.34))
        base = ImageEnhance.Color(base).enhance(0.82)
        base = ImageEnhance.Contrast(base).enhance(1.08)
        base = base.filter(ImageFilter.GaussianBlur(18)).convert("RGBA")

        shade = Image.new("RGBA", size, (9, 12, 18, 160))
        glow = Image.new("RGBA", size, (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow)
        glow_draw.ellipse((-20, -40, 420, 360), fill=(255, 151, 102, 52))
        glow_draw.ellipse((520, 80, 1010, 600), fill=(79, 123, 255, 48))
        glow = glow.filter(ImageFilter.GaussianBlur(84))

        base.alpha_composite(shade)
        base.alpha_composite(glow)
        return base

    def _create_photo_card(self, source: Image.Image, size: tuple[int, int]) -> Image.Image:
        card = ImageOps.fit(source, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.3))
        card = ImageEnhance.Contrast(card).enhance(1.05)
        card = ImageEnhance.Sharpness(card).enhance(1.2)
        card = card.convert("RGBA")

        gradient = Image.new("RGBA", size, (0, 0, 0, 0))
        gradient_draw = ImageDraw.Draw(gradient)
        for index in range(size[1]):
            alpha = int(170 * max(0, (index - size[1] * 0.42) / (size[1] * 0.58)))
            gradient_draw.line((0, index, size[0], index), fill=(8, 10, 14, alpha))
        card.alpha_composite(gradient)

        rounded = self._mask_with_radius(card, radius=34)
        return self._add_shadow_and_border(rounded, border=(255, 255, 255, 34), shadow=(0, 0, 0, 120), radius=34)

    def _create_panel_art(self, size: tuple[int, int]) -> Image.Image:
        image = Image.new("RGBA", size, (0, 0, 0, 0))
        shadow = Image.new("RGBA", size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        shadow_draw.rounded_rectangle((20, 24, size[0] - 18, size[1] - 10), radius=38, fill=(0, 0, 0, 95))
        shadow = shadow.filter(ImageFilter.GaussianBlur(26))
        image.alpha_composite(shadow)

        panel = Image.new("RGBA", size, (0, 0, 0, 0))
        panel_draw = ImageDraw.Draw(panel)
        panel_draw.rounded_rectangle((12, 10, size[0] - 12, size[1] - 14), radius=36, fill=(18, 24, 35, 228), outline=self.PANEL_EDGE, width=2)

        top_glow = Image.new("RGBA", size, (0, 0, 0, 0))
        top_glow_draw = ImageDraw.Draw(top_glow)
        top_glow_draw.ellipse((16, -110, size[0] - 16, 160), fill=(255, 255, 255, 30))
        top_glow = top_glow.filter(ImageFilter.GaussianBlur(34))

        accent = Image.new("RGBA", size, (0, 0, 0, 0))
        accent_draw = ImageDraw.Draw(accent)
        accent_draw.ellipse((size[0] - 140, 40, size[0] + 40, 220), fill=(255, 150, 112, 28))
        accent_draw.ellipse((-40, size[1] - 230, 180, size[1] - 40), fill=(76, 123, 255, 26))
        accent = accent.filter(ImageFilter.GaussianBlur(28))

        image.alpha_composite(panel)
        image.alpha_composite(top_glow)
        image.alpha_composite(accent)
        return image

    def _create_button_art(
        self,
        size: tuple[int, int],
        fill_rgb: tuple[int, int, int],
        light_shift: float,
        press_offset: int,
    ) -> Image.Image:
        image = Image.new("RGBA", size, (0, 0, 0, 0))
        shadow = Image.new("RGBA", size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        shadow_draw.rounded_rectangle((12, 14 + press_offset, size[0] - 12, size[1] - 6 + press_offset), radius=22, fill=(0, 0, 0, 82))
        shadow = shadow.filter(ImageFilter.GaussianBlur(12))
        image.alpha_composite(shadow)

        fill = blend_rgb(fill_rgb, (255, 255, 255), max(light_shift, 0))
        if light_shift < 0:
            fill = blend_rgb(fill_rgb, (0, 0, 0), abs(light_shift))

        button_layer = Image.new("RGBA", size, (0, 0, 0, 0))
        button_draw = ImageDraw.Draw(button_layer)
        rect = (8, 8 + press_offset, size[0] - 8, size[1] - 10 + press_offset)
        button_draw.rounded_rectangle(rect, radius=22, fill=(*fill, 255), outline=(255, 255, 255, 24), width=1)

        highlight = Image.new("RGBA", size, (0, 0, 0, 0))
        highlight_draw = ImageDraw.Draw(highlight)
        highlight_draw.rounded_rectangle((12, 10 + press_offset, size[0] - 12, size[1] // 2 + press_offset), radius=20, fill=(255, 255, 255, 20))
        highlight = highlight.filter(ImageFilter.GaussianBlur(10))

        image.alpha_composite(button_layer)
        image.alpha_composite(highlight)
        return image

    @staticmethod
    def _mask_with_radius(image: Image.Image, radius: int) -> Image.Image:
        mask = Image.new("L", image.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle((0, 0, image.size[0], image.size[1]), radius=radius, fill=255)
        rounded = image.copy()
        rounded.putalpha(mask)
        return rounded

    @staticmethod
    def _add_shadow_and_border(
        image: Image.Image,
        border: tuple[int, int, int, int],
        shadow: tuple[int, int, int, int],
        radius: int,
    ) -> Image.Image:
        canvas = Image.new("RGBA", (image.size[0] + 24, image.size[1] + 24), (0, 0, 0, 0))

        shadow_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_layer)
        shadow_draw.rounded_rectangle((10, 10, canvas.size[0] - 10, canvas.size[1] - 10), radius=radius + 8, fill=shadow)
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(16))
        canvas.alpha_composite(shadow_layer)

        canvas.alpha_composite(image, dest=(12, 12))
        border_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        border_draw = ImageDraw.Draw(border_layer)
        border_draw.rounded_rectangle((12, 12, canvas.size[0] - 12, canvas.size[1] - 12), radius=radius, outline=border, width=2)
        canvas.alpha_composite(border_layer)
        return canvas


def run_self_test() -> int:
    engine = CalculatorEngine()

    def press_many(*keys: str) -> str:
        for key in keys:
            engine.press(key)
        return engine.display_state().result

    assert press_many("1", "2", "+", "7", "=") == "19"
    engine.clear()
    assert press_many("9", "%") == "0.09"
    engine.clear()
    assert press_many("5", "*", "+/-", "2", "=") == "-10"
    engine.clear()
    assert press_many("1", ".", "5", "+", "2", ".", "5", "=") == "4"
    engine.clear()
    press_many("8", "8", "DEL")
    assert engine.display_state().result == "8"
    print("Self-test OK")
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        return run_self_test()

    try:
        root = tk.Tk()
        CalculatorApp(root)
        root.mainloop()
    except FileNotFoundError as exc:
        messagebox.showerror(APP_TITLE, str(exc))
        return 1
    except Exception as exc:  # vb ciao mi sn scocciato mi fermo QUI
        messagebox.showerror(APP_TITLE, f"Avvio fallito:\n{exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
