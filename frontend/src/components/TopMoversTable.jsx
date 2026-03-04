import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { formatCurrency, formatPercent } from "../utils/formatters";

function TopMoversTable({ items }) {
  return (
    <div className="panel">
      <div className="border-b border-line/70 px-5 py-4">
        <p className="label">Market Movement</p>
        <h3 className="mt-1 text-lg font-semibold text-slate-50">Top Movers</h3>
      </div>

      <div className="table-shell rounded-none border-0 bg-transparent">
        <table>
          <thead>
            <tr>
              <th>Product</th>
              <th>Change</th>
              <th>Direction</th>
              <th>New Price</th>
            </tr>
          </thead>
          <tbody>
            {items.slice(0, 10).map((item) => (
              <tr key={`${item.product_id}-${item.created_at}`}>
                <td className="font-medium text-slate-100">{item.product_name}</td>
                <td className={item.direction === "up" ? "text-success" : "text-warning"}>
                  {formatPercent(item.percentage_change)}
                </td>
                <td>
                  <span className="inline-flex items-center gap-2">
                    {item.direction === "up" ? (
                      <ArrowUpRight size={16} className="text-success" />
                    ) : (
                      <ArrowDownRight size={16} className="text-warning" />
                    )}
                    <span className="text-slate-200">{item.direction === "up" ? "Up" : "Down"}</span>
                  </span>
                </td>
                <td>{formatCurrency(item.new_price)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default TopMoversTable;
