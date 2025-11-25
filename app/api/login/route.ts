import { NextRequest, NextResponse } from "next/server";
import jwt from "jsonwebtoken";
import { cookies } from "next/headers"; 

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const { username, password, rememberMe } = await req.json();

  const ADMIN_USERNAME = process.env.ADMIN_USERNAME || "gold";
  const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || "rich";
  const JWT_SECRET = process.env.JWT_SECRET || "your_secret_key";

  if (username === ADMIN_USERNAME && password === ADMIN_PASSWORD) {
 
    const expiresInStr = rememberMe ? "7d" : "1h"; 
    const maxAgeSeconds = rememberMe ? 7 * 24 * 60 * 60 : 3600; 

    
    const token = jwt.sign({ username }, JWT_SECRET, { expiresIn: expiresInStr });

    cookies().set({
      name: "token",
      value: token,
      httpOnly: true, 
      secure: process.env.NODE_ENV === "production", 
      path: "/", 
      maxAge: maxAgeSeconds, 
    });

    return NextResponse.json({ success: true, token });
  } else {
    return NextResponse.json({ error: "Username or Password is Wrong" }, { status: 401 });
  }
}