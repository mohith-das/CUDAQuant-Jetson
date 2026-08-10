import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../api";

export default function Experiments() {
  const { data: exps, isLoading } = useQuery({
    queryKey: ["experiments"],
    queryFn: () => apiFetch<Array<Record<string,unknown>>>("/api/experiments/"),
    refetchInterval: 5000,
  });

  if (isLoading) return <p>Loading experiments...</p>;

  return (
    <div>
      <h2>Experiments</h2>
      {exps && exps.length > 0 ? (
        <table>
          <thead><tr><th>ID</th><th>Hypothesis</th><th>Status</th><th>Origin</th><th>Metrics</th></tr></thead>
          <tbody>
            {exps.map((e: Record<string,unknown>) => (
              <tr key={e.experiment_id as string}>
                <td>{e.experiment_id as string}</td>
                <td>{(e.hypothesis as string)?.slice(0, 60)}</td>
                <td>{e.status as string}</td>
                <td>{e.origin as string}</td>
                <td>{JSON.stringify(e.metrics)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p>No experiments yet. Use the API to propose one.</p>
      )}
    </div>
  );
}
