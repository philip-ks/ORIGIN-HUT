const rawBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL
  ?? "http://localhost:4000";

export const API_BASE_URL =
  rawBaseUrl.replace(
    /\/$/,
    ""
  );


export class ApiError extends Error {

  status: number;

  payload: unknown;


  constructor(
    status: number,
    payload: unknown
  ) {

    super(
      `Origin Hut API request failed with status ${status}.`
    );

    this.name =
      "ApiError";

    this.status =
      status;

    this.payload =
      payload;

  }

}


export async function apiGet<T>(
  path: string
): Promise<T> {

  const response =
    await fetch(
      API_BASE_URL
      + path,
      {
        cache:
          "no-store"
      }
    );


  let payload:
    unknown;


  try {

    payload =
      await response.json();

  }
  catch {

    payload = null;

  }


  if (!response.ok) {

    throw new ApiError(
      response.status,
      payload
    );

  }


  return payload as T;

}
