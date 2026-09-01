import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_INTERNAL_URL || "http://127.0.0.1:8000";
const API_KEY = process.env.CAJACLARAD_API_KEY || "dev-secret-key";

export async function GET(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const targetPath = path.join("/");
  const search = request.nextUrl.search;
  const url = `${BACKEND_URL}/${targetPath}${search}`;

  try {
    const res = await fetch(url, {
      method: "GET",
      headers: {
        "X-API-Key": API_KEY,
        Accept: request.headers.get("Accept") || "application/json",
      },
      cache: "no-store",
    });

    const contentType = res.headers.get("content-type") || "application/json";
    const data = await res.arrayBuffer();

    return new NextResponse(data, {
      status: res.status,
      headers: {
        "Content-Type": contentType,
        "Content-Disposition": res.headers.get("content-disposition") || "",
      },
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Error interno en proxy";
    return NextResponse.json({ detail: `Proxy Error: ${message}` }, { status: 502 });
  }
}

export async function POST(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const targetPath = path.join("/");
  const search = request.nextUrl.search;
  const url = `${BACKEND_URL}/${targetPath}${search}`;

  try {
    const body = await request.text();
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "X-API-Key": API_KEY,
        "Content-Type": request.headers.get("content-type") || "application/json",
      },
      body: body || undefined,
    });

    const data = await res.arrayBuffer();
    return new NextResponse(data, {
      status: res.status,
      headers: {
        "Content-Type": res.headers.get("content-type") || "application/json",
      },
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Error interno en proxy";
    return NextResponse.json({ detail: `Proxy Error: ${message}` }, { status: 502 });
  }
}
