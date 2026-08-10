import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../api";

export default function ModelRegistry() {
  const { data: models, isLoading } = useQuery({
    queryKey: ["models"],
    queryFn: () => apiFetch<Array<Record<string,unknown>>>("/api/models/"),
    refetchInterval: 10000,
  });

  if (isLoading) return <p>Loading models...</p>;

  return (
    <div>
      <h2>Model Registry</h2>
      {models && models.length > 0 ? (
        <table>
          <thead><tr><th>ID</th><th>Family</th><th>Version</th><th>Status</th><th>Actions</th></tr></thead>
          <tbody>
            {models.map((m: Record<string,unknown>) => (
              <tr key={m.model_id as string}>
                <td>{m.model_id as string}</td>
                <td>{m.family as string}</td>
                <td>{m.version as number}</td>
                <td><strong>{m.status as string}</strong></td>
                <td>
                  {m.status === "candidate" && (
                    <button onClick={() => apiFetch(`/api/models/${m.model_id}/promote`, {method:"POST"})}>Promote</button>
                  )}
                  {m.status === "challenger" && (
                    <button onClick={() => apiFetch(`/api/models/${m.model_id}/promote`, {method:"POST"})}>Make Champion</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p>No models registered yet.</p>
      )}
    </div>
  );
}
