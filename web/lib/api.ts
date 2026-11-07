export type ApiHealth = { status: string };

export async function getApiHealth(): Promise<ApiHealth> {
  const response = await fetch('/api/health', { cache: 'no-store' });
  if (!response.ok) throw new Error(`API indisponivel (${response.status})`);
  return response.json() as Promise<ApiHealth>;
}
