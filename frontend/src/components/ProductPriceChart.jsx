import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { compactDateTime, formatCurrency } from "../utils/formatters";

const palette = ["#5fd1ff", "#f5b942", "#3dd68c", "#ff6b81", "#9f7aea"];

function buildSeries(points = []) {
  const grouped = new Map();
  const competitors = new Set();

  points.forEach((point) => {
    const key = new Date(point.timestamp).toISOString();
    const entry = grouped.get(key) || { timestamp: point.timestamp };

    if (point.our_price !== null && point.our_price !== undefined) {
      entry.ourPrice = Number(point.our_price);
    }
    if (point.competitor_name) {
      const field = point.competitor_name.replace(/\s+/g, "_");
      competitors.add(field);
      entry[field] = Number(point.competitor_price);
    }

    grouped.set(key, entry);
  });

  return {
    data: Array.from(grouped.values()).sort((left, right) => new Date(left.timestamp) - new Date(right.timestamp)),
    competitorKeys: Array.from(competitors),
  };
}

function ProductPriceChart({ points }) {
  const { data, competitorKeys } = buildSeries(points);

  return (
    <div className="panel h-[28rem] p-5">
      <p className="label">Historical Pricing</p>
      <h3 className="mt-1 text-lg font-semibold text-slate-50">Our Price vs Competitors</h3>

      <div className="mt-6 h-[21rem]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid stroke="rgba(142, 166, 188, 0.12)" />
            <XAxis dataKey="timestamp" tickFormatter={compactDateTime} stroke="#8ea6bc" minTickGap={28} />
            <YAxis stroke="#8ea6bc" tickFormatter={(value) => `₹${Number(value).toFixed(0)}`} width={72} />
            <Tooltip
              contentStyle={{
                background: "#101c28",
                border: "1px solid #22384a",
                borderRadius: "16px",
              }}
              labelFormatter={(value) => compactDateTime(value)}
              formatter={(value, name) => [formatCurrency(value), name]}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="ourPrice"
              name="Our Price"
              stroke="#5fd1ff"
              strokeWidth={3}
              dot={false}
              connectNulls
            />
            {competitorKeys.map((key, index) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                name={key.replace(/_/g, " ")}
                stroke={palette[(index + 1) % palette.length]}
                strokeWidth={2}
                dot={false}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default ProductPriceChart;
