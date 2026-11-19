export async function api(
  path,
  { token, body, ...options } = {}
) {
  const headers = {
    ...(body !== undefined
      ? { "Content-Type": "application/json" }
      : {}),
    ...(token
      ? { Authorization: `Bearer ${token}` }
      : {}),
  };

  const response = await fetch(`/api${path}`, {
    ...options,
    headers,
    ...(body !== undefined
      ? { body: JSON.stringify(body) }
      : {}),
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const error = new Error(
      data.message || data.msg || "The request failed."
    );

    error.status = response.status;
    throw error;
  }

  return data;
}