"use client";
import React, { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { FaUser, FaLock } from "react-icons/fa";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  
  // 1. เพิ่ม State สำหรับ Remember Me
  const [rememberMe, setRememberMe] = useState(false); 
  
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const router = useRouter();

  const passwordRef = useRef<HTMLInputElement>(null);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    try {
      const res = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // 2. ส่งค่า rememberMe ไปที่ API พร้อม username/password
        body: JSON.stringify({ username, password, rememberMe }), 
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.error || "Login failed");
        return;
      }

      setSuccess("Login successful!");
      router.push("/market");
    } catch (err: any) {
      setError("Network error");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500 relative">
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm z-0" />

      <div className="relative z-10 bg-white/10 backdrop-blur-2xl p-10 rounded-3xl shadow-2xl w-full max-w-sm">
        
        <h2 className="text-4xl font-bold text-white text-center mb-8">
          Sign In
        </h2>

        <form onSubmit={handleLogin} className="flex flex-col gap-5">

          <div className="relative">
            <FaUser className="absolute left-3 top-3 text-white/70" />
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Username"
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  passwordRef.current?.focus();
                }
              }}
              className="pl-10 pr-4 py-2 rounded-lg bg-white/20 text-white border border-white/40 w-full outline-none focus:ring-2 focus:ring-white/80"
            />
          </div>

          <div className="relative">
            <FaLock className="absolute left-3 top-3 text-white/70" />
            <input
              ref={passwordRef}
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              className="pl-10 pr-4 py-2 rounded-lg bg-white/20 text-white border border-white/40 w-full outline-none focus:ring-2 focus:ring-white/80"
            />
          </div>

          <div className="flex items-center gap-2 ml-1">
            <input
              id="remember-me"
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              className="w-4 h-4 rounded bg-white/20 border-white/40 text-purple-600 focus:ring-purple-500 cursor-pointer accent-purple-500"
            />
            <label htmlFor="remember-me" className="text-white text-sm cursor-pointer select-none">
              Remember me (7 days)
            </label>
          </div>

          <button
            type="submit"
            className="py-2 bg-white text-purple-600 font-semibold rounded-lg hover:bg-purple-100 transition transform hover:scale-105"
          >
            Sign In
          </button>
        </form>

        {error && <p className="text-red-400 mt-3 text-center">{error}</p>}
        {success && <p className="text-green-400 mt-3 text-center">{success}</p>}
      </div>
    </div>
  );
}