import { NextRequest, NextResponse } from "next/server";
import jwt from "jsonwebtoken";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const { username, password } = await req.json();

  const ADMIN_USERNAME = process.env.ADMIN_USERNAME || "gold";
  const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || "rich";
  const JWT_SECRET = process.env.JWT_SECRET || "your_secret_key";

  if (username === ADMIN_USERNAME && password === ADMIN_PASSWORD) {
    const token = jwt.sign({ username }, JWT_SECRET, { expiresIn: "1h" });
    return NextResponse.json({ token });
  } else {
    return NextResponse.json({ error: "Username or Password is Wrong" }, { status: 401 });
  }
}