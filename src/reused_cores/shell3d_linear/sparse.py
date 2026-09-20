"""Small dependency-free sparse matrix primitives for the P6 global system.

Rows store only nonzero entries. The sequence interface preserves read-only
``matrix[i][j]`` compatibility for verification code without materializing a
dense matrix; production matvec and solve paths use ``row_items`` directly.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence


class SparseRow(Sequence[float]):
    __slots__ = ("_entries", "_size")

    def __init__(self, size: int, entries: Mapping[int, float]) -> None:
        self._size = size
        self._entries = dict(entries)

    def __len__(self) -> int:
        return self._size

    def __getitem__(self, index: int | slice) -> float | tuple[float, ...]:
        if isinstance(index, slice):
            return tuple(self[position] for position in range(*index.indices(self._size)))
        position = index + self._size if index < 0 else index
        if position < 0 or position >= self._size:
            raise IndexError("sparse row index out of range")
        return self._entries.get(position, 0.0)

    def __iter__(self) -> Iterator[float]:
        for column in range(self._size):
            yield self._entries.get(column, 0.0)

    def items(self) -> tuple[tuple[int, float], ...]:
        return tuple(sorted(self._entries.items()))


class SparseMatrix(Sequence[SparseRow]):
    """Immutable square row-sparse matrix with a read-only sequence facade."""

    __slots__ = ("_rows", "size")

    def __init__(self, rows: Sequence[Mapping[int, float]]) -> None:
        self.size = len(rows)
        frozen: list[SparseRow] = []
        for row_index, row in enumerate(rows):
            entries: dict[int, float] = {}
            for column, value in row.items():
                if column < 0 or column >= self.size:
                    raise ValueError(f"sparse column {column} is outside row {row_index}")
                number = float(value)
                if number != 0.0:
                    entries[column] = number
            frozen.append(SparseRow(self.size, entries))
        self._rows = tuple(frozen)

    @classmethod
    def from_dense(cls, matrix: Sequence[Sequence[float]]) -> SparseMatrix:
        size = len(matrix)
        if any(len(row) != size for row in matrix):
            raise ValueError("sparse conversion requires a square matrix")
        return cls(
            [
                {column: float(value) for column, value in enumerate(row) if value != 0.0}
                for row in matrix
            ]
        )

    def __len__(self) -> int:
        return self.size

    def __getitem__(self, index: int | slice) -> SparseRow | tuple[SparseRow, ...]:
        return self._rows[index]

    def row_items(self, row: int) -> tuple[tuple[int, float], ...]:
        return self._rows[row].items()

    @property
    def nonzero_count(self) -> int:
        return sum(len(row.items()) for row in self._rows)

    def matvec(self, vector: Sequence[float]) -> tuple[float, ...]:
        if len(vector) != self.size:
            raise ValueError("sparse matrix and vector sizes are incompatible")
        return tuple(
            sum(value * vector[column] for column, value in row.items()) for row in self._rows
        )

    def symmetry_error(self) -> float:
        worst = 0.0
        scale = 0.0
        for row, entries in enumerate(self._rows):
            for column, value in entries.items():
                scale = max(scale, abs(value))
                if column > row:
                    worst = max(worst, abs(value - self._rows[column][row]))
        return 0.0 if scale == 0.0 else worst / scale

    def to_dense(self) -> tuple[tuple[float, ...], ...]:
        return tuple(tuple(row) for row in self._rows)


__all__ = ["SparseMatrix", "SparseRow"]
