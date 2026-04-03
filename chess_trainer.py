#!/usr/bin/env python3
"""Chess trainer with multiple exercise modes and a free-play board."""

from __future__ import annotations

import math
import random
import tkinter as tk
from datetime import date
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

FILES = "abcdefgh"
RANKS = "12345678"
SQUARES = [f"{f}{r}" for r in RANKS for f in FILES]

LIGHT = "#f0d9b5"
DARK = "#b58863"
SEL = "#4aa3ff"
GOOD = "#5cb85c"
BAD = "#d9534f"
HINT = "#f7e36a"
DEMO = "#7b61ff"

# Максимально реалистичная оценка числа уникальных задач для этой программы.
# Часть режимов имеет точное число вариантов, для сложных режимов берём верхнюю оценку.
COORD_TASKS = 64
COLOR_TASKS = 2
DIAGONAL_TASKS = 64
STARTING_TASKS = 12
GEOMETRY_TASKS = 64 * 5
# Верхняя оценка для режима контроля: расстановка 6 фигур на разных клетках,
# 16 вариантов фигур/цветов на клетку и выбор стороны для контроля.
CONTROL_TASKS_UPPER = (math.factorial(64) // math.factorial(58)) * (16 ** 6) * 2
# Верхняя оценка для мысленных перемещений: 4 фигуры, 64 старта, до 4 шагов при макс. ветвлении ферзя.
MENTAL_TASKS_UPPER = 4 * 64 * (27 ** 4)
# Пешки: 2 цвета * 8 файлов * 6 рангов * 4 комбинации взятий.
PAWN_TASKS_UPPER = 2 * 8 * 6 * 4
# Свободный режим не имеет конечного числа сценариев, поэтому здесь его не ограничиваем.
MAX_REAL_TASKS = (
    COORD_TASKS
    + COLOR_TASKS
    + DIAGONAL_TASKS
    + STARTING_TASKS
    + GEOMETRY_TASKS
    + CONTROL_TASKS_UPPER
    + MENTAL_TASKS_UPPER
    + PAWN_TASKS_UPPER
)

PIECE_SYMBOLS = {
    "wK": "♔", "wQ": "♕", "wR": "♖", "wB": "♗", "wN": "♘", "wP": "♙",
    "bK": "♚", "bQ": "♛", "bR": "♜", "bB": "♝", "bN": "♞", "bP": "♟",
}

START_BOARD = {
    **{f"{f}2": "wP" for f in FILES},
    **{f"{f}7": "bP" for f in FILES},
    "a1": "wR", "h1": "wR", "a8": "bR", "h8": "bR",
    "b1": "wN", "g1": "wN", "b8": "bN", "g8": "bN",
    "c1": "wB", "f1": "wB", "c8": "bB", "f8": "bB",
    "d1": "wQ", "d8": "bQ", "e1": "wK", "e8": "bK",
}


class Mode(Enum):
    COORDS = "Координаты"
    COLOR = "Цвет клетки"
    DIAGONALS = "Диагонали"
    STARTING = "Расстановка фигур"
    GEOMETRY = "Геометрия фигур"
    CONTROL = "Контроль поля"
    MENTAL = "Мысленные перемещения"
    PAWN = "Обучение всем ходам"
    FREE = "Свободный режим"


@dataclass
class Task:
    number: int
    prompt: str
    expected: Set[str]
    multi: bool
    board: Optional[Dict[str, str]] = None
    hint: str = ""
    explain: str = ""
    target_piece: str = ""
    control_side: str = ""
    required_board: Optional[Dict[str, str]] = None
    demo_path: Optional[List[str]] = None
    challenge_path: Optional[List[str]] = None
    piece_name: str = ""


def sq_to_xy(square: str) -> Tuple[int, int]:
    x = FILES.index(square[0])
    y = 7 - RANKS.index(square[1])
    return x, y


def xy_to_sq(x: int, y: int) -> str:
    return f"{FILES[x]}{RANKS[7-y]}"


def on_board(x: int, y: int) -> bool:
    return 0 <= x < 8 and 0 <= y < 8


def square_color(square: str) -> str:
    x, y = sq_to_xy(square)
    return "light" if (x + y) % 2 == 0 else "dark"


def ray_moves(x: int, y: int, dirs: List[Tuple[int, int]], board: Dict[str, str], side: str) -> Set[str]:
    out: Set[str] = set()
    for dx, dy in dirs:
        cx, cy = x + dx, y + dy
        while on_board(cx, cy):
            sq = xy_to_sq(cx, cy)
            occ = board.get(sq)
            if occ:
                if occ[0] != side:
                    out.add(sq)
                break
            out.add(sq)
            cx += dx
            cy += dy
    return out


def piece_attacks(piece: str, square: str, board: Optional[Dict[str, str]] = None) -> Set[str]:
    board = board or {}
    side, kind = piece[0], piece[1]
    x, y = sq_to_xy(square)
    out: Set[str] = set()

    if kind == "N":
        for dx, dy in [(-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)]:
            nx, ny = x + dx, y + dy
            if on_board(nx, ny):
                sq = xy_to_sq(nx, ny)
                if board.get(sq, "").startswith(side):
                    continue
                out.add(sq)
    elif kind == "K":
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if on_board(nx, ny):
                    sq = xy_to_sq(nx, ny)
                    if board.get(sq, "").startswith(side):
                        continue
                    out.add(sq)
    elif kind == "B":
        out |= ray_moves(x, y, [(-1, -1), (-1, 1), (1, -1), (1, 1)], board, side)
    elif kind == "R":
        out |= ray_moves(x, y, [(-1, 0), (1, 0), (0, -1), (0, 1)], board, side)
    elif kind == "Q":
        out |= ray_moves(x, y, [(-1, -1), (-1, 1), (1, -1), (1, 1), (-1, 0), (1, 0), (0, -1), (0, 1)], board, side)
    elif kind == "P":
        d = 1 if side == "w" else -1
        for dx in (-1, 1):
            nx, ny = x + dx, y - d
            if on_board(nx, ny):
                out.add(xy_to_sq(nx, ny))
    return out


def pawn_moves(piece: str, square: str, board: Dict[str, str]) -> Set[str]:
    side = piece[0]
    x, y = sq_to_xy(square)
    d = -1 if side == "w" else 1
    out: Set[str] = set()
    one = (x, y + d)
    if on_board(*one):
        one_sq = xy_to_sq(*one)
        if one_sq not in board:
            out.add(one_sq)
            start_rank = 6 if side == "w" else 1
            two = (x, y + 2 * d)
            if y == start_rank and on_board(*two):
                two_sq = xy_to_sq(*two)
                if two_sq not in board:
                    out.add(two_sq)
    for dx in (-1, 1):
        nx, ny = x + dx, y + d
        if on_board(nx, ny):
            sq = xy_to_sq(nx, ny)
            if board.get(sq, "").startswith("b" if side == "w" else "w"):
                out.add(sq)
    return out


class ChessTrainer(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Шахматный тренажёр")
        self.geometry("1200x820")
        self.resizable(True, True)
        self.minsize(980, 680)

        self.lang = "ru"
        self.is_fullscreen = False
        self.cell_size = 80
        self.board_offset_x = 0
        self.board_offset_y = 0
        self.board_flipped = False
        self.palette_height = 190
        self.palette_y = 0
        self.palette_rects: Dict[str, Tuple[int, int, int, int]] = {}
        self.drag_piece: Optional[str] = None
        self.drag_pos: Optional[Tuple[int, int]] = None

        self.mode_order = list(Mode)
        self.mode_index = 0
        self.mode = self.mode_order[self.mode_index]
        self.hints = True
        self.selected: Set[str] = set()
        self.feedback: Dict[str, str] = {}
        self.demo_marks: Dict[str, str] = {}
        self.task: Optional[Task] = None
        self.board: Dict[str, str] = dict(START_BOARD)
        self.free_selected_from: Optional[str] = None
        self.edit_selected_from: Optional[str] = None
        self.geometry_demo_phase = False
        self.mental_demo_phase = False
        self.task_counter = 0
        self.last_result_ok = False

        self._build_ui()
        self.bind("<space>", lambda _e: self.next_mode())
        self.bind("<h>", lambda _e: self.toggle_hints())
        self.bind("<H>", lambda _e: self.toggle_hints())
        self.bind("<r>", lambda _e: self.new_task())
        self.bind("<R>", lambda _e: self.new_task())
        self.bind("<d>", lambda _e: self.run_demo())
        self.bind("<D>", lambda _e: self.run_demo())
        self.bind("<l>", lambda _e: self.toggle_language())
        self.bind("<L>", lambda _e: self.toggle_language())
        self.bind("<F11>", lambda _e: self.toggle_fullscreen())
        self.bind("<Escape>", lambda _e: self.exit_fullscreen())

        self.new_task()

    def _build_ui(self) -> None:
        root = tk.Frame(self)
        root.pack(fill="both", expand=True, padx=12, pady=12)

        self.canvas = tk.Canvas(root, width=640, height=640, bg="white", highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_left_press)
        self.canvas.bind("<B1-Motion>", self.on_left_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_release)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Configure>", lambda _e: self.draw())

        side = tk.Frame(root, width=320)
        side.pack(side="right", fill="y")

        self.mode_label = tk.Label(side, text="", font=("Arial", 20, "bold"), wraplength=300, justify="left")
        self.mode_label.pack(anchor="w", pady=(0, 12))

        self.task_label = tk.Label(side, text="", font=("Arial", 15), wraplength=300, justify="left")
        self.task_label.pack(anchor="w", pady=(0, 12))

        self.hint_label = tk.Label(side, text="", font=("Arial", 12), wraplength=300, justify="left", fg="#666")
        self.hint_label.pack(anchor="w", pady=(0, 16))

        self.result_label = tk.Label(side, text="", font=("Arial", 13, "bold"), wraplength=300, justify="left")
        self.result_label.pack(anchor="w", pady=(0, 16))

        self.explain_label = tk.Label(side, text="", font=("Arial", 12), wraplength=300, justify="left", fg="#333")
        self.explain_label.pack(anchor="w", pady=(0, 14))

        self.controls_label = tk.Label(side, text="", justify="left", anchor="w", wraplength=300, font=("Arial", 12))
        self.controls_label.pack(anchor="w")

        self.lang_button = tk.Button(side, text="EN", command=self.toggle_language, font=("Arial", 12, "bold"))
        self.lang_button.pack(anchor="w", pady=(10, 0))

        self.rotate_button = tk.Button(side, text="↻ Поворот доски", command=self.toggle_board_rotation, font=("Arial", 12, "bold"))
        self.rotate_button.pack(anchor="w", pady=(10, 0))

        self.editor_piece_var = tk.StringVar(value="wP")
        editor_values = ["wP", "wN", "wB", "wR", "wQ", "wK", "bP", "bN", "bB", "bR", "bQ", "bK"]
        self.editor_menu = tk.OptionMenu(side, self.editor_piece_var, *editor_values)
        self.editor_menu.config(font=("Arial", 11))
        self.editor_menu.pack(anchor="w", pady=(10, 0))

    def _t(self, ru: str, en: str) -> str:
        return en if self.lang == "en" else ru

    def mode_title(self) -> str:
        titles = {
            Mode.COORDS: ("Координаты", "Coordinates"),
            Mode.COLOR: ("Цвет клетки", "Square color"),
            Mode.DIAGONALS: ("Диагонали", "Diagonals"),
            Mode.STARTING: ("Расстановка фигур", "Starting squares"),
            Mode.GEOMETRY: ("Геометрия фигур", "Piece geometry"),
            Mode.CONTROL: ("Контроль поля", "Square control"),
            Mode.MENTAL: ("Мысленные перемещения", "Mental moves"),
            Mode.PAWN: ("Обучение всем ходам", "All-piece move training"),
            Mode.FREE: ("Свободный режим", "Free mode"),
        }
        ru, en = titles[self.mode]
        return self._t(ru, en)

    def controls_text(self) -> str:
        return self._t(
            "Управление:\nSPACE — следующий режим\nH — подсказки вкл/выкл\nR — новая задача\nD — демонстрация правильного решения\nL — язык RU/EN\nF11 — полный экран\nESC — выход из полного экрана\nЛКМ — выбор/перемещение\nПКМ — убрать фигуру (в режимах редактирования)\nВнизу: перетащите фигуру с панели на доску",
            "Controls:\nSPACE — next mode\nH — hints on/off\nR — new task\nD — show demo solution\nL — language RU/EN\nF11 — fullscreen\nESC — exit fullscreen\nLMB — select/move\nRMB — remove piece (in edit modes)\nBottom panel: drag a piece onto board",
        )

    def toggle_language(self) -> None:
        self.lang = "en" if self.lang == "ru" else "ru"
        self.localize_current_task_text()
        self.update_labels()
        self.draw()

    def localize_current_task_text(self) -> None:
        if not self.task:
            return

        task = self.task

        if self.mode == Mode.COORDS:
            sq = next(iter(task.expected), "")
            task.prompt = self._t(f"Найдите клетку: {sq}", f"Find square: {sq}")
            task.hint = self._t(f"Координата: {sq}", f"Coordinate: {sq}")
            task.explain = self._t(
                f"Объяснение простыми словами: буква {sq[0]} — столбец, цифра {sq[1]} — ряд. Нужна ровно клетка {sq}.",
                f"Simple: file is {sq[0]}, rank is {sq[1]}. You need exactly square {sq}.",
            )
            return

        if self.mode == Mode.DIAGONALS and task.board:
            s, piece = next(iter(task.board.items()))
            if piece == "wR":
                task.prompt = self._t(
                    f"Прямые линии ладьи: отметьте все клетки хода с {s}",
                    f"Rook lines: mark all legal rook line squares from {s}",
                )
                task.hint = self._t("Для ладьи — только вертикаль и горизонталь", "For rook: only file and rank lines")
                task.explain = self._t(
                    "Этот подрежим специально тренирует прямые линии ладьи.",
                    "This submode specifically trains rook straight lines.",
                )
            else:
                who_ru = "слона" if piece == "wB" else "ферзя"
                who_en = "bishop" if piece == "wB" else "queen"
                task.prompt = self._t(
                    f"Диагонали: отметьте все диагональные клетки для {who_ru} из {s}",
                    f"Diagonals: mark all diagonal squares for {who_en} from {s}",
                )
                task.hint = self._t("Только диагонали, без вертикалей/горизонталей", "Only diagonals, no vertical/horizontal")
                task.explain = self._t(
                    "Режим диагоналей тренирует именно диагональные лучи, отдельно от общей геометрии фигур.",
                    "Diagonals mode trains diagonal rays separately from general piece geometry.",
                )
            return

        if self.mode == Mode.STARTING:
            if task.required_board:
                side = "w" if any(v.startswith("w") for v in task.required_board.values()) else "b"
                squares_text = ", ".join(sorted(task.required_board.keys()))
                task.prompt = self._t(
                    f"Свободная расстановка: расставьте ВСЕ фигуры стороны {'белые' if side == 'w' else 'чёрные'} на стартовые клетки.",
                    f"Free setup: place ALL {('white' if side == 'w' else 'black')} pieces on starting squares.",
                )
                task.hint = self._t(f"Нужно точно заполнить клетки: {squares_text}", f"Fill exact squares: {squares_text}")
                task.explain = self._t(
                    "Это свободный режим внутри расстановки: перетаскивайте фигуры мышью с панели снизу. Ошибки покажутся красным, верные клетки — зелёным.",
                    "This is a free setup drill: drag pieces from the bottom palette. Errors are red, correct squares are green.",
                )
            elif task.target_piece:
                piece = task.target_piece
                side_ru = "белую" if piece[0] == "w" else "чёрную"
                side_en = "white" if piece[0] == "w" else "black"
                names_ru = {"K": "короля", "Q": "ферзя", "R": "ладью", "B": "слона", "N": "коня", "P": "пешку"}
                names_en = {"K": "king", "Q": "queen", "R": "rook", "B": "bishop", "N": "knight", "P": "pawn"}
                cells = ", ".join(sorted(task.expected))
                if len(task.expected) == 1:
                    task.prompt = self._t(
                        f"Поставьте {side_ru} {names_ru[piece[1]]} на клетку {cells}.",
                        f"Place {side_en} {names_en[piece[1]]} on square {cells}.",
                    )
                else:
                    task.prompt = self._t(
                        f"Поставьте ВСЕ {len(task.expected)} {side_ru} {names_ru[piece[1]]} на клетки: {cells}.",
                        f"Place ALL {len(task.expected)} {side_en} {names_en[piece[1]]} pieces on squares: {cells}.",
                    )
                task.hint = self._t(f"Точные клетки: {cells}", f"Exact squares: {cells}")
                task.explain = self._t(
                    "Перетаскивайте фигуры с нижней панели. Нужные клетки перечислены в задании, поэтому не надо угадывать 'какая стартовая'.",
                    "Drag pieces from the bottom palette. Required squares are listed explicitly.",
                )
            return

        if self.mode == Mode.GEOMETRY and task.board:
            sq, piece = next(iter(task.board.items()))
            names_ru = {"N": "коня", "B": "слона", "R": "ладьи", "Q": "ферзя", "K": "короля"}
            task.prompt = self._t(
                f"Геометрия фигур: отметьте все ходы {names_ru[piece[1]]} с {sq} (чистая геометрия, без других фигур).",
                f"Piece geometry: mark all legal moves from {sq} on an empty board.",
            )
            task.hint = self._t(
                "Здесь изучается базовая геометрия хода фигуры на пустой доске",
                "This mode studies pure move geometry on an empty board",
            )
            task.explain = self._t(
                "Отдельный режим от 'Диагоналей' и 'Обучения всем ходам': только базовая форма хода фигуры.",
                "Separate from diagonals/all-moves: only the base move shape of each piece.",
            )
            return

        if self.mode == Mode.CONTROL and task.control_side:
            task.prompt = self._t(
                f"Кликните все клетки под боем стороны {'белыми' if task.control_side == 'w' else 'чёрными'}",
                f"Mark all squares controlled by {('white' if task.control_side == 'w' else 'black')} side",
            )
            task.hint = self._t("Нужно отметить каждую атакуемую клетку", "Mark every attacked square")
            task.explain = self._t(
                "Цель: по текущей позиции отметить ВСЕ клетки, которые сторона может атаковать следующим ходом. Позиция фиксированная: просто анализируйте и отмечайте поля под боем.",
                "Goal: in this fixed position mark ALL squares this side can attack on the next move.",
            )
            return

        if self.mode == Mode.MENTAL and task.board:
            sq, piece = next(iter(task.board.items()))
            names_ru = {"N": "конь", "B": "слон", "R": "ладья", "Q": "ферзь"}
            task.prompt = self._t(
                f"Мысленные перемещения: та же фигура '{names_ru[piece[1]]}'. После демонстрации (D) решите задание на новом поле со старта {sq}.",
                f"Mental moves: same piece. After demo (D), solve on a new square from {sq}.",
            )
            task.hint = self._t(f"Задание идёт по скрытой траектории от {sq}", f"Task follows a hidden route from {sq}")
            task.explain = self._t(
                "Сначала демонстрация пути на одном поле, затем аналогичное задание без демонстрации на другом поле.",
                "First: route demo on one square. Then: same-piece task on another square without demo.",
            )
            return

        if self.mode == Mode.PAWN and task.board:
            sq, piece = next(iter(task.board.items()))
            task.prompt = self._t(
                f"Обучение всем ходам: выберите все легальные ходы для фигуры {piece} с {sq}",
                f"All-piece training: mark all legal moves for {piece} from {sq}",
            )
            task.hint = self._t(
                "Учитывайте и обычные ходы, и взятия, и блокировки фигурами",
                "Consider normal moves, captures, and blockers",
            )
            task.explain = self._t(
                "Этот режим тренирует ходы ВСЕХ фигур. Нажмите D для демонстрации корректных клеток, затем повторите самостоятельно.",
                "This mode trains moves of ALL pieces. Press D for demo squares, then repeat on your own.",
            )

    def toggle_fullscreen(self) -> None:
        self.is_fullscreen = not self.is_fullscreen
        self.attributes("-fullscreen", self.is_fullscreen)

    def toggle_board_rotation(self) -> None:
        self.board_flipped = not self.board_flipped
        self.draw()

    def exit_fullscreen(self) -> None:
        if self.is_fullscreen:
            self.is_fullscreen = False
            self.attributes("-fullscreen", False)

    def _board_metrics(self) -> Tuple[int, int, int]:
        w = max(self.canvas.winfo_width(), 1)
        h = max(self.canvas.winfo_height(), 1)
        board_space_h = max(h - self.palette_height, 8)
        board_px = min(w, board_space_h)
        self.cell_size = max(board_px // 8, 1)
        board_px = self.cell_size * 8
        self.board_offset_x = (w - board_px) // 2
        self.board_offset_y = max((board_space_h - board_px) // 2, 0)
        self.palette_y = self.board_offset_y + board_px + 10
        return self.cell_size, self.board_offset_x, self.board_offset_y

    def _display_to_board_coords(self, x: int, y: int) -> Tuple[int, int]:
        if self.board_flipped:
            return 7 - x, 7 - y
        return x, y

    def _board_to_display_coords(self, x: int, y: int) -> Tuple[int, int]:
        if self.board_flipped:
            return 7 - x, 7 - y
        return x, y

    def _is_edit_mode(self) -> bool:
        return self.mode in {Mode.STARTING}

    def _recompute_control_expected(self) -> None:
        if not self.task or self.mode != Mode.CONTROL or not self.task.control_side:
            return
        exp: Set[str] = set()
        for sq, p in self.board.items():
            if p[0] == self.task.control_side:
                exp |= piece_attacks(p, sq, self.board)
        self.task.expected = exp

    def _palette_piece_at(self, x: int, y: int) -> Optional[str]:
        for piece, (x0, y0, x1, y1) in self.palette_rects.items():
            if x0 <= x <= x1 and y0 <= y <= y1:
                return piece
        return None

    def on_left_press(self, event: tk.Event) -> None:
        if self._is_edit_mode():
            palette_piece = self._palette_piece_at(event.x, event.y)
            if palette_piece:
                self.drag_piece = palette_piece
                self.drag_pos = (event.x, event.y)
                self.draw()
                return
        self.on_click(event)

    def on_left_motion(self, event: tk.Event) -> None:
        if self.drag_piece:
            self.drag_pos = (event.x, event.y)
            self.draw()

    def on_left_release(self, event: tk.Event) -> None:
        if not self.drag_piece:
            return
        piece = self.drag_piece
        self.drag_piece = None
        self.drag_pos = None

        cell, off_x, off_y = self._board_metrics()
        dx = (event.x - off_x) // cell
        dy = (event.y - off_y) // cell
        if on_board(dx, dy):
            x, y = self._display_to_board_coords(dx, dy)
            sq = xy_to_sq(x, y)
            self.board[sq] = piece
            if self.mode == Mode.CONTROL:
                self._recompute_control_expected()
            if self.mode == Mode.STARTING:
                self.evaluate_starting_task()
        self.draw()

    def next_mode(self) -> None:
        self.mode_index = (self.mode_index + 1) % len(self.mode_order)
        self.mode = self.mode_order[self.mode_index]
        self.new_task()

    def toggle_hints(self) -> None:
        self.hints = not self.hints
        self.update_labels()
        self.draw()

    def new_task(self) -> None:
        self.selected = set()
        self.feedback = {}
        self.demo_marks = {}
        self.free_selected_from = None
        self.edit_selected_from = None
        self.geometry_demo_phase = False
        self.mental_demo_phase = False
        self.last_result_ok = False
        self.task_counter += 1
        if self.mode == Mode.FREE:
            self.task = Task(
                number=self.task_counter,
                prompt=self._t(
                    "Свободная игра: выберите фигуру и затем клетку назначения.",
                    "Free play: select a piece and then a destination square.",
                ),
                expected=set(),
                multi=False,
                board=dict(START_BOARD),
                explain=self._t(
                    "Свободный режим: сначала клик по фигуре, потом по клетке назначения.",
                    "Free mode: first click a piece, then click destination square.",
                )
            )
            self.board = dict(START_BOARD)
        else:
            self.task = self.generate_task(self.mode)
            self.board = dict(self.task.board or {})
            if self.mode == Mode.STARTING and self.task.target_piece:
                self.editor_piece_var.set(self.task.target_piece)
            if self.mode == Mode.GEOMETRY:
                self.geometry_demo_phase = True
            if self.mode == Mode.MENTAL:
                self.mental_demo_phase = True
        self.update_labels()
        self.draw()

    def generate_task(self, mode: Mode) -> Task:
        if mode == Mode.COORDS:
            sq = random.choice(SQUARES)
            return Task(
                number=self.task_counter,
                prompt=self._t(f"Найдите клетку: {sq}", f"Find square: {sq}"),
                expected={sq},
                multi=False,
                board={},
                hint=self._t(f"Координата: {sq}", f"Coordinate: {sq}"),
                explain=self._t(
                    f"Объяснение простыми словами: буква {sq[0]} — столбец, цифра {sq[1]} — ряд. Нужна ровно клетка {sq}.",
                    f"Simple: file is {sq[0]}, rank is {sq[1]}. You need exactly square {sq}.",
                )
            )

        if mode == Mode.COLOR:
            c = random.choice(["light", "dark"])
            txt = "светлую" if c == "light" else "тёмную"
            pool = {sq for sq in SQUARES if square_color(sq) == c}
            variant = random.choice(["any", "file", "rank"])

            if variant == "file":
                file = random.choice(FILES)
                expected = {sq for sq in pool if sq[0] == file}
                prompt = self._t(f"Кликните {txt} клетку на вертикали {file}", f"Click a {c} square on file {file}")
                hint = self._t(f"Нужна {txt} клетка на линии {file}", f"Need a {c} square on file {file}")
            elif variant == "rank":
                rank = random.choice(RANKS)
                expected = {sq for sq in pool if sq[1] == rank}
                prompt = self._t(f"Кликните {txt} клетку на горизонтали {rank}", f"Click a {c} square on rank {rank}")
                hint = self._t(f"Нужна {txt} клетка на линии {rank}", f"Need a {c} square on rank {rank}")
            else:
                expected = pool
                prompt = self._t(f"Кликните любую {txt} клетку", f"Click any {c} square")
                hint = self._t(f"Нужно выбрать {txt} клетку", f"Choose a {c} square")

            return Task(
                number=self.task_counter,
                prompt=prompt,
                expected=expected,
                multi=False,
                board={},
                hint=hint,
                explain=self._t(
                    "Смотри на условие и цвет клетки. Если задана линия (буква/цифра), клетка должна одновременно подходить и по цвету, и по линии.",
                    "Read condition and color. If file/rank is specified, the square must match both color and line.",
                ),
            )

        if mode == Mode.DIAGONALS:
            s = random.choice(SQUARES)
            piece = random.choice(["wB", "wQ", "wR"])
            if piece == "wR":
                exp = piece_attacks(piece, s, {})
                prompt = f"Прямые линии ладьи: отметьте все клетки хода с {s}"
                hint = "Для ладьи — только вертикаль и горизонталь"
                explain = "Этот подрежим специально тренирует прямые линии ладьи."
            else:
                x, y = sq_to_xy(s)
                exp = set()
                for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                    nx, ny = x + dx, y + dy
                    while on_board(nx, ny):
                        exp.add(xy_to_sq(nx, ny))
                        nx += dx
                        ny += dy
                who = "слона" if piece == "wB" else "ферзя"
                prompt = f"Диагонали: отметьте все диагональные клетки для {who} из {s}"
                hint = "Только диагонали, без вертикалей/горизонталей"
                explain = "Режим диагоналей тренирует именно диагональные лучи, отдельно от общей геометрии фигур."

            if self.lang == "en":
                if piece == "wR":
                    prompt = f"Rook lines: mark all legal rook line squares from {s}"
                    hint = "For rook: only file and rank lines"
                    explain = "This submode specifically trains rook straight lines."
                else:
                    who_en = "bishop" if piece == "wB" else "queen"
                    prompt = f"Diagonals: mark all diagonal squares for {who_en} from {s}"
                    hint = "Only diagonals, no vertical/horizontal"
                    explain = "Diagonals mode trains diagonal rays separately from general piece geometry."
            return Task(
                number=self.task_counter,
                prompt=prompt,
                expected=exp,
                multi=True,
                board={s: piece},
                hint=hint,
                explain=explain,
            )

        if mode == Mode.STARTING:
            starts = {
                "wK": ["e1"], "wQ": ["d1"], "wR": ["a1", "h1"], "wB": ["c1", "f1"], "wN": ["b1", "g1"], "wP": [f"{f}2" for f in FILES],
                "bK": ["e8"], "bQ": ["d8"], "bR": ["a8", "h8"], "bB": ["c8", "f8"], "bN": ["b8", "g8"], "bP": [f"{f}7" for f in FILES],
            }
            variant = random.choice(["piece", "free_setup"])
            if variant == "free_setup":
                side = random.choice(["w", "b"])
                side_name = "белые" if side == "w" else "чёрные"
                required_board = {sq: p for sq, p in START_BOARD.items() if p[0] == side}
                squares_text = ", ".join(sorted(required_board.keys()))
                return Task(
                    number=self.task_counter,
                    prompt=self._t(
                        f"Свободная расстановка: расставьте ВСЕ фигуры стороны {side_name} на стартовые клетки.",
                        f"Free setup: place ALL {('white' if side == 'w' else 'black')} pieces on starting squares.",
                    ),
                    expected=set(required_board.keys()),
                    multi=False,
                    board={},
                    hint=self._t(f"Нужно точно заполнить клетки: {squares_text}", f"Fill exact squares: {squares_text}"),
                    explain=self._t(
                        "Это свободный режим внутри расстановки: перетаскивайте фигуры мышью с панели снизу. Ошибки покажутся красным, верные клетки — зелёным.",
                        "This is a free setup drill: drag pieces from the bottom palette. Errors are red, correct squares are green.",
                    ),
                    required_board=required_board,
                )

            piece = random.choice(list(starts))
            exp = set(starts[piece])
            side = "белую" if piece[0] == "w" else "чёрную"
            side_en = "white" if piece[0] == "w" else "black"
            names = {"K": "короля", "Q": "ферзя", "R": "ладью", "B": "слона", "N": "коня", "P": "пешку"}
            names_en = {"K": "king", "Q": "queen", "R": "rook", "B": "bishop", "N": "knight", "P": "pawn"}
            cells = ", ".join(sorted(exp))
            if len(exp) == 1:
                prompt = f"Поставьте {side} {names[piece[1]]} на клетку {cells}."
                prompt_en = f"Place {side_en} {names_en[piece[1]]} on square {cells}."
            else:
                prompt = f"Поставьте ВСЕ {len(exp)} {side} {names[piece[1]]} на клетки: {cells}."
                prompt_en = f"Place ALL {len(exp)} {side_en} {names_en[piece[1]]} pieces on squares: {cells}."
            return Task(
                number=self.task_counter,
                prompt=self._t(prompt, prompt_en),
                expected=exp,
                multi=False,
                board={},
                hint=self._t(f"Точные клетки: {cells}", f"Exact squares: {cells}"),
                explain=self._t(
                    "Перетаскивайте фигуры с нижней панели. Нужные клетки перечислены в задании, поэтому не надо угадывать 'какая стартовая'.",
                    "Drag pieces from the bottom palette. Required squares are listed explicitly.",
                ),
                target_piece=piece,
            )

        if mode == Mode.GEOMETRY:
            sq = random.choice(SQUARES)
            piece = random.choice(["wN", "wB", "wR", "wQ", "wK"])
            exp = piece_attacks(piece, sq, {})
            names = {"N": "конь", "B": "слон", "R": "ладья", "Q": "ферзь", "K": "король"}
            return Task(
                number=self.task_counter,
                prompt=self._t(
                    f"Геометрия фигур: отметьте все ходы {names[piece[1]]} с {sq} (чистая геометрия, без других фигур).",
                    f"Piece geometry: mark all legal moves from {sq} on an empty board.",
                ),
                expected=exp,
                multi=True,
                board={sq: piece},
                hint=self._t("Здесь изучается базовая геометрия хода фигуры на пустой доске", "This mode studies pure move geometry on an empty board"),
                explain=self._t(
                    "Отдельный режим от 'Диагоналей' и 'Обучения всем ходам': только базовая форма хода фигуры.",
                    "Separate from diagonals/all-moves: only the base move shape of each piece.",
                ),
            )

        if mode == Mode.CONTROL:
            board = {}
            pieces = ["wQ", "wR", "wB", "wN", "wK", "wP", "wP", "wP"]
            random.shuffle(pieces)
            placed = random.sample(SQUARES, 6)
            for i, sq in enumerate(placed):
                p = pieces[i]
                board[sq] = p if random.random() > 0.35 else p.replace("w", "b")
            side = random.choice(["w", "b"])
            exp: Set[str] = set()
            for sq, p in board.items():
                if p[0] == side:
                    if p[1] == "P":
                        exp |= piece_attacks(p, sq, board)
                    else:
                        exp |= piece_attacks(p, sq, board)
            team = "белыми" if side == "w" else "чёрными"
            return Task(
                number=self.task_counter,
                prompt=self._t(f"Кликните все клетки под боем стороны {team}", f"Mark all squares controlled by {('white' if side == 'w' else 'black')} side"),
                expected=exp,
                multi=True,
                board=board,
                hint=self._t("Нужно отметить каждую атакуемую клетку", "Mark every attacked square"),
                explain=self._t(
                    "Цель: по текущей позиции отметить ВСЕ клетки, которые сторона может атаковать следующим ходом. Позиция фиксированная: просто анализируйте и отмечайте поля под боем.",
                    "Goal: in this fixed position mark ALL squares this side can attack on the next move.",
                ),
                control_side=side,
            )

        if mode == Mode.MENTAL:
            piece = random.choice(["wN", "wB", "wR", "wQ"])
            demo_start = random.choice(SQUARES)
            demo_path = [demo_start]
            cur = demo_start
            for _ in range(random.randint(2, 4)):
                moves = list(piece_attacks(piece, cur, {}))
                if not moves:
                    break
                cur = random.choice(moves)
                demo_path.append(cur)

            challenge_start = random.choice([sq for sq in SQUARES if sq != demo_start])
            challenge_path = [challenge_start]
            cur = challenge_start
            for _ in range(random.randint(2, 4)):
                moves = list(piece_attacks(piece, cur, {}))
                if not moves:
                    break
                cur = random.choice(moves)
                challenge_path.append(cur)

            exp = {challenge_path[-1]}
            names = {"N": "конь", "B": "слон", "R": "ладья", "Q": "ферзь"}
            return Task(
                number=self.task_counter,
                prompt=self._t(
                    f"Мысленные перемещения: та же фигура '{names[piece[1]]}'. После демонстрации (D) решите задание на новом поле со старта {challenge_start}.",
                    f"Mental moves: same piece. After demo (D), solve on a new square from {challenge_start}.",
                ),
                expected=exp,
                multi=False,
                board={challenge_start: piece},
                hint=self._t(f"Задание идёт по скрытой траектории от {challenge_start}", f"Task follows a hidden route from {challenge_start}"),
                explain=self._t(
                    "Сначала демонстрация пути на одном поле, затем аналогичное задание без демонстрации на другом поле.",
                    "First: route demo on one square. Then: same-piece task on another square without demo.",
                ),
                demo_path=demo_path,
                challenge_path=challenge_path,
            )

        # ALL-PIECE MOVE TRAINING
        side = random.choice(["w", "b"])
        kind = random.choice(["P", "N", "B", "R", "Q", "K"])
        sq = random.choice(SQUARES)
        board = {sq: f"{side}{kind}"}
        for block_sq in random.sample([x for x in SQUARES if x != sq], 6):
            if random.random() > 0.55:
                block_side = side if random.random() > 0.5 else ("b" if side == "w" else "w")
                block_kind = random.choice(["P", "N", "B", "R", "Q"])
                board[block_sq] = f"{block_side}{block_kind}"

        piece = f"{side}{kind}"
        exp = pawn_moves(piece, sq, board) if kind == "P" else piece_attacks(piece, sq, board)
        side_text = "белой" if side == "w" else "чёрной"
        names = {"P": "пешки", "N": "коня", "B": "слона", "R": "ладьи", "Q": "ферзя", "K": "короля"}
        return Task(
            number=self.task_counter,
            prompt=self._t(
                f"Обучение всем ходам: выберите все легальные ходы для {side_text} {names[kind]} с {sq}",
                f"All-piece training: mark all legal moves for {piece} from {sq}",
            ),
            expected=exp,
            multi=True,
            board=board,
            hint=self._t("Учитывайте и обычные ходы, и взятия, и блокировки фигурами", "Consider normal moves, captures, and blockers"),
            explain=self._t(
                "Этот режим тренирует ходы ВСЕХ фигур. Нажмите D для демонстрации корректных клеток, затем повторите самостоятельно.",
                "This mode trains moves of ALL pieces. Press D for demo squares, then repeat on your own.",
            ),
        )

    def update_labels(self) -> None:
        assert self.task is not None
        year = date.today().year
        mode_text = self._t("Режим", "Mode")
        task_text = self._t("Задача", "Task")
        of_text = self._t("из", "of")
        self.mode_label.config(
            text=f"{mode_text}: {self.mode_title()}\n{task_text} {self.task.number} {of_text} {MAX_REAL_TASKS:,} ({year})"
        )
        self.task_label.config(text=self.task.prompt)
        hint = self.task.hint if self.hints else self._t("Подсказки выключены", "Hints are off")
        self.hint_label.config(text=f"{self._t('Подсказка', 'Hint')}: {hint}")
        self.explain_label.config(text=f"{self._t('Пояснение для новичка', 'Beginner explanation')}:\n{self.task.explain}")
        self.controls_label.config(text=self.controls_text())
        self.lang_button.config(text=("EN" if self.lang == "ru" else "RU"))
        self.rotate_button.config(text=self._t("↻ Поворот доски", "↻ Rotate board"))
        if self._is_edit_mode():
            self.editor_menu.config(state="normal")
        else:
            self.editor_menu.config(state="disabled")

        if self.mode == Mode.GEOMETRY and self.geometry_demo_phase:
            self.result_label.config(
                text=self._t(
                    "Показ ходов активен: запомните подсветку и кликните по доске для повтора.",
                    "Move demo is active: memorize highlighted squares and click board to repeat.",
                ),
                fg=DEMO,
            )
        if self.mode == Mode.MENTAL and self.mental_demo_phase:
            self.result_label.config(
                text=self._t(
                    "Шаг 1: нажмите D и посмотрите демонстрацию маршрута. Шаг 2: решите новую траекторию без показа.",
                    "Step 1: press D to view route demo. Step 2: solve a new route without demo.",
                ),
                fg=DEMO,
            )

    def on_click(self, event: tk.Event) -> None:
        cell, off_x, off_y = self._board_metrics()
        dx = (event.x - off_x) // cell
        dy = (event.y - off_y) // cell
        if not on_board(dx, dy):
            return
        x, y = self._display_to_board_coords(dx, dy)
        sq = xy_to_sq(x, y)

        if self.mode == Mode.FREE:
            self.handle_free_move(sq)
            self.draw()
            return

        if self._is_edit_mode():
            self.handle_edit_click(sq)
            self.draw()
            return

        if self.mode == Mode.GEOMETRY and self.geometry_demo_phase:
            self.geometry_demo_phase = False
            self.selected = set()
            self.feedback = {}
            self.result_label.config(
                text=self._t("Теперь повторите без подсказок.", "Now repeat without hints."),
                fg="#333",
            )
            self.draw()
            return

        if self.mode == Mode.MENTAL and self.mental_demo_phase:
            self.mental_demo_phase = False
            self.result_label.config(
                text=self._t(
                    "Теперь решите задачу на другом поле без демонстрации.",
                    "Now solve the task on another square without demonstration.",
                ),
                fg="#333",
            )

        assert self.task is not None
        if self.task.multi:
            if sq in self.selected:
                self.selected.remove(sq)
            else:
                self.selected.add(sq)
            if len(self.selected) >= len(self.task.expected):
                self.evaluate()
        else:
            self.selected = {sq}
            self.evaluate()
        self.draw()

    def on_right_click(self, event: tk.Event) -> None:
        if not self._is_edit_mode():
            return
        cell, off_x, off_y = self._board_metrics()
        dx = (event.x - off_x) // cell
        dy = (event.y - off_y) // cell
        if not on_board(dx, dy):
            return
        x, y = self._display_to_board_coords(dx, dy)
        sq = xy_to_sq(x, y)
        if sq in self.board:
            self.board.pop(sq, None)
            self.edit_selected_from = None
            if self.mode == Mode.CONTROL:
                self._recompute_control_expected()
            if self.mode == Mode.STARTING:
                self.evaluate_starting_task()
            self.draw()

    def handle_edit_click(self, sq: str) -> None:
        self.selected = set()
        self.feedback = {}
        piece = self.board.get(sq)
        if self.edit_selected_from:
            moving = self.board.get(self.edit_selected_from)
            if moving:
                self.board[sq] = moving
                self.board.pop(self.edit_selected_from, None)
            self.edit_selected_from = None
        elif piece:
            self.edit_selected_from = sq
            self.editor_piece_var.set(piece)
        else:
            self.board[sq] = self.editor_piece_var.get()

        if self.mode == Mode.CONTROL:
            self._recompute_control_expected()
        if self.mode == Mode.STARTING:
            self.evaluate_starting_task()

    def handle_free_move(self, sq: str) -> None:
        piece = self.board.get(sq)
        if self.free_selected_from is None:
            if piece:
                self.free_selected_from = sq
                self.result_label.config(
                    text=self._t(
                        f"Выбрана фигура {PIECE_SYMBOLS[piece]} на {sq}",
                        f"Selected {PIECE_SYMBOLS[piece]} on {sq}",
                    ),
                    fg="#222",
                )
            else:
                self.result_label.config(
                    text=self._t("Пустая клетка. Сначала выберите фигуру.", "Empty square. Select a piece first."),
                    fg=BAD,
                )
            return

        src = self.free_selected_from
        moving = self.board.get(src)
        self.free_selected_from = None
        if not moving:
            self.result_label.config(
                text=self._t("Фигура исчезла, выберите снова.", "Piece is no longer there, select again."),
                fg=BAD,
            )
            return
        legal = pawn_moves(moving, src, self.board) if moving[1] == "P" else piece_attacks(moving, src, self.board)
        if sq in legal:
            self.board[sq] = moving
            self.board.pop(src, None)
            self.result_label.config(text=self._t(f"✅ Верный ход: {src} → {sq}", f"✅ Correct move: {src} → {sq}"), fg=GOOD)
        else:
            self.result_label.config(text=self._t(f"❌ Неверный ход: {src} → {sq}", f"❌ Wrong move: {src} → {sq}"), fg=BAD)

    def evaluate(self) -> None:
        assert self.task is not None
        exp, got = self.task.expected, self.selected
        self.feedback = {}

        if not self.task.multi:
            chosen = next(iter(got), None)
            ok = chosen is not None and chosen in exp
            if chosen is not None:
                self.feedback[chosen] = GOOD if ok else BAD
            if not ok and exp:
                self.feedback[next(iter(exp))] = HINT
        else:
            ok = True
            for sq in got - exp:
                self.feedback[sq] = BAD
                ok = False
            for sq in exp & got:
                self.feedback[sq] = GOOD
            for sq in exp - got:
                self.feedback[sq] = HINT
                ok = False
            ok = ok and len(got) == len(exp)

        if ok:
            self.last_result_ok = True
            self.result_label.config(text=self._t("✅ Правильно! Нажмите R для новой задачи.", "✅ Correct! Press R for a new task."), fg=GOOD)
            self.after(1200, self._auto_next_after_success)
        else:
            self.last_result_ok = False
            self.result_label.config(
                text=self._t("❌ Есть ошибки. Красные — неверно, жёлтые — пропущено.", "❌ Mistakes found. Red = wrong, yellow = missed."),
                fg=BAD,
            )

    def evaluate_starting_task(self) -> None:
        if not self.task:
            return
        self.feedback = {}
        ok = True

        if self.task.required_board:
            required = self.task.required_board
            for sq, need_piece in required.items():
                current = self.board.get(sq)
                if current == need_piece:
                    self.feedback[sq] = GOOD
                else:
                    ok = False
                    self.feedback[sq] = BAD if current else HINT
            for sq, piece in self.board.items():
                if sq not in required and piece in required.values():
                    self.feedback[sq] = BAD
                    ok = False
        else:
            target = self.task.target_piece
            expected = self.task.expected
            for sq in expected:
                if self.board.get(sq) == target:
                    self.feedback[sq] = GOOD
                else:
                    self.feedback[sq] = HINT
                    ok = False
            for sq, piece in self.board.items():
                if piece == target and sq not in expected:
                    self.feedback[sq] = BAD
                    ok = False

        if ok:
            self.last_result_ok = True
            self.result_label.config(
                text=self._t("✅ Верно расставлено. Следующая задача откроется автоматически.", "✅ Correct setup. Next task will open automatically."),
                fg=GOOD,
            )
            self.after(1200, self._auto_next_after_success)
        else:
            self.last_result_ok = False
            self.result_label.config(
                text=self._t("❌ Пока не верно. Красные клетки — ошибка, жёлтые — недостающие.", "❌ Not yet. Red = wrong placement, yellow = missing piece."),
                fg=BAD,
            )

    def _auto_next_after_success(self) -> None:
        if self.last_result_ok and self.mode != Mode.FREE:
            self.new_task()

    def run_demo(self) -> None:
        if self.mode == Mode.FREE or not self.task:
            self.result_label.config(
                text=self._t(
                    "Демо в свободном режиме не нужно: здесь вы играете сами.",
                    "Demo is not needed in free mode: you play by yourself.",
                ),
                fg="#333",
            )
            return
        if self.mode == Mode.MENTAL:
            if self.mental_demo_phase and self.task.demo_path:
                path = self.task.demo_path
                self.demo_marks = {sq: DEMO for sq in path}
                self.result_label.config(
                    text=self._t(
                        f"Демонстрация траектории: {' → '.join(path)}",
                        f"Trajectory demo: {' → '.join(path)}",
                    ),
                    fg=DEMO,
                )
            else:
                self.result_label.config(
                    text=self._t(
                        "Для второго этапа демонстрация отключена: решите путь самостоятельно.",
                        "Demo is disabled on stage 2: solve route by yourself.",
                    ),
                    fg=BAD,
                )
            self.draw()
            return
        self.demo_marks = {sq: DEMO for sq in self.task.expected}
        ordered = sorted(self.task.expected, key=lambda s: (s[1], s[0]))
        if ordered:
            step_text = " → ".join(ordered)
            self.result_label.config(text=self._t(f"Демонстрация решения: {step_text}", f"Solution demo: {step_text}"), fg=DEMO)
        self.draw()

    def draw(self) -> None:
        self.canvas.delete("all")
        cell, off_x, off_y = self._board_metrics()
        self.palette_rects = {}
        for y in range(8):
            for x in range(8):
                sq = xy_to_sq(x, y)
                color = LIGHT if square_color(sq) == "light" else DARK
                dx, dy = self._board_to_display_coords(x, y)
                x0 = off_x + dx * cell
                y0 = off_y + dy * cell
                x1 = x0 + cell
                y1 = y0 + cell
                self.canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline=color)

                show_hint = self.hints and self.task and sq in self.task.expected and self.mode != Mode.FREE
                if self.mode == Mode.GEOMETRY and not self.geometry_demo_phase:
                    show_hint = False
                if self.mode == Mode.GEOMETRY and self.geometry_demo_phase and self.task and sq in self.task.expected:
                    show_hint = True
                if show_hint:
                    self.canvas.create_rectangle(
                        x0 + cell * 0.25,
                        y0 + cell * 0.25,
                        x0 + cell * 0.75,
                        y0 + cell * 0.75,
                        outline=HINT,
                        width=2,
                    )

                if sq in self.selected:
                    self.canvas.create_rectangle(x0 + 2, y0 + 2, x1 - 2, y1 - 2, outline=SEL, width=3)
                if self.edit_selected_from == sq:
                    self.canvas.create_rectangle(x0 + 2, y0 + 2, x1 - 2, y1 - 2, outline=DEMO, width=3)
                if sq in self.feedback:
                    self.canvas.create_rectangle(x0 + 6, y0 + 6, x1 - 6, y1 - 6, outline=self.feedback[sq], width=4)
                if sq in self.demo_marks:
                    self.canvas.create_rectangle(x0 + 12, y0 + 12, x1 - 12, y1 - 12, outline=self.demo_marks[sq], width=3)

                piece = self.board.get(sq)
                if piece:
                    self.canvas.create_text(
                        x0 + cell / 2,
                        y0 + cell / 2,
                        text=PIECE_SYMBOLS[piece],
                        font=("Arial", max(int(cell * 0.55), 16)),
                    )

                if y == 7:
                    self.canvas.create_text(
                        x0 + cell - 10,
                        y1 - 10,
                        text=sq[0],
                        font=("Arial", max(int(cell * 0.12), 9)),
                        fill="#333",
                    )
                if x == 0:
                    self.canvas.create_text(
                        x0 + 10,
                        y0 + 10,
                        text=sq[1],
                        font=("Arial", max(int(cell * 0.12), 9)),
                        fill="#333",
                    )

        top_side = self._t("Сторона чёрных", "Black side") if not self.board_flipped else self._t("Сторона белых", "White side")
        bottom_side = self._t("Сторона белых", "White side") if not self.board_flipped else self._t("Сторона чёрных", "Black side")
        board_px = cell * 8
        self.canvas.create_text(
            off_x + board_px / 2,
            max(off_y - 14, 8),
            text=top_side,
            font=("Arial", 10, "bold"),
            fill="#444",
        )
        self.canvas.create_text(
            off_x + board_px / 2,
            off_y + board_px + 14,
            text=bottom_side,
            font=("Arial", 10, "bold"),
            fill="#444",
        )

        palette_pieces = ["wP", "wN", "wB", "wR", "wQ", "wK", "bP", "bN", "bB", "bR", "bQ", "bK"]
        pw = max(int(cell * 0.75), 34)
        ph = max(int(cell * 0.75), 34)
        gap_x = 8
        gap_y = 16
        canvas_w = max(self.canvas.winfo_width(), 320)
        columns = max(4, min(len(palette_pieces), (canvas_w - 16) // (pw + gap_x)))
        rows = math.ceil(len(palette_pieces) / columns)
        total_w = columns * pw + (columns - 1) * gap_x
        start_x = max((canvas_w - total_w) // 2, 8)
        y0 = self.palette_y

        for i, piece in enumerate(palette_pieces):
            row = i // columns
            col = i % columns
            x0 = start_x + col * (pw + gap_x)
            box_y = y0 + row * (ph + gap_y + 18)
            x1, y1 = x0 + pw, box_y + ph
            self.palette_rects[piece] = (x0, box_y, x1, y1)
            self.canvas.create_rectangle(x0, box_y, x1, y1, outline="#666", width=1, fill="#f7f7f7")
            self.canvas.create_text(x0 + pw / 2, box_y + ph / 2 - 5, text=PIECE_SYMBOLS[piece], font=("Arial", max(int(ph * 0.55), 14)))
            self.canvas.create_text(
                x0 + pw / 2,
                y1 + 10,
                text=piece,
                font=("Arial", 11, "bold"),
                fill="#222",
            )

        if self.drag_piece and self.drag_pos:
            dx, dy = self.drag_pos
            self.canvas.create_text(
                dx,
                dy,
                text=PIECE_SYMBOLS[self.drag_piece],
                font=("Arial", max(int(cell * 0.6), 18)),
                fill="#111",
            )


if __name__ == "__main__":
    random.seed()
    app = ChessTrainer()
    app.mainloop()