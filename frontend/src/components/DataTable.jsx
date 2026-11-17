import { cx } from "../utils";

export default function DataTable({
  columns,
  rows,
  sort,
  onSort,
  rowKey,
  rowClassName,
  empty,
  caption,
  containerClassName,
  selection,
}) {
  return (
    <div className={cx("overflow-x-auto", containerClassName)}>
      <table className="min-w-full border-collapse">
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-900/80">
            {selection ? (
              <th scope="col" className="th w-10">
                <input
                  type="checkbox"
                  aria-label="Select all rows"
                  checked={selection.allSelected}
                  ref={(element) => {
                    if (element) {
                      element.indeterminate = selection.someSelected && !selection.allSelected;
                    }
                  }}
                  onChange={(event) => selection.onToggleAll?.(event.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-rr-600 focus:ring-rr-500 dark:border-slate-600 dark:bg-slate-800"
                />
              </th>
            ) : null}
            {columns.map((column) => {
              const active = sort?.key === column.key;
              const ariaSort = active
                ? sort.dir === "asc"
                  ? "ascending"
                  : "descending"
                : "none";
              return (
                <th
                  key={column.key}
                  scope="col"
                  aria-sort={column.sortable ? ariaSort : undefined}
                  className={cx(
                    "th",
                    column.align === "right" && "text-right",
                    column.align === "center" && "text-center",
                    column.headerClassName,
                  )}
                >
                  {column.sortable ? (
                    <button
                      type="button"
                      onClick={() => onSort?.(column.key)}
                      className={cx(
                        "inline-flex items-center gap-1 rounded font-semibold transition-colors hover:text-slate-900 dark:hover:text-white",
                        column.align === "right" && "flex-row-reverse",
                        active && "text-rr-700 dark:text-rr-300",
                      )}
                      title={`Sort by ${column.label}`}
                    >
                      {column.label}
                      <span aria-hidden="true" className="text-[9px]">
                        {active ? (sort.dir === "asc" ? "▲" : "▼") : "↕"}
                      </span>
                    </button>
                  ) : (
                    column.label
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800/70">
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              className={cx(
                "transition-colors hover:bg-slate-50/70 dark:hover:bg-slate-800/40",
                rowClassName?.(row),
              )}
            >
              {selection ? (
                <td className="td w-10">
                  <input
                    type="checkbox"
                    aria-label={`Select ${row.name ?? "row"}`}
                    checked={selection.selected.has(rowKey(row))}
                    onChange={(event) => selection.onToggle?.(rowKey(row), event.target.checked)}
                    className="h-4 w-4 rounded border-slate-300 text-rr-600 focus:ring-rr-500 dark:border-slate-600 dark:bg-slate-800"
                  />
                </td>
              ) : null}
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={cx(
                    "td text-slate-700 dark:text-slate-300",
                    column.align === "right" && "text-right",
                    column.align === "center" && "text-center",
                    column.cellClassName,
                  )}
                >
                  {column.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 ? empty : null}
    </div>
  );
}
