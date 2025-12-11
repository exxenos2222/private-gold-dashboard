'use client'
import { useState, useRef, useEffect } from 'react'
import { FaRobot, FaPaperPlane, FaTimes } from 'react-icons/fa';

export default function ChatPanel() {
    const [selectedSymbol, setSelectedSymbol] = useState("GOLD");
    const [selectedMode, setSelectedMode] = useState("daytrade");

    const [messages, setMessages] = useState([
        { role: 'bot', text: 'สวัสดีครับ 👋 ผมพร้อมวางแผนเทรดแล้ว เลือกโหมดด้านบนได้เลย!' }
    ]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const messagesEndRef = useRef(null);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    const sendMessage = async (e) => {
        e.preventDefault();
        if (!input.trim()) return;
        await processRequest(input);
        setInput('');
    };

    const requestAnalysis = async () => {
        const userText = `ขอแผน ${selectedSymbol} แบบ ${selectedMode}`;
        await processRequest(userText);
    };

    const processRequest = async (text) => {
        setLoading(true);
        setMessages(prev => [...prev, { role: 'user', text: text }]);

        try {
            const res = await fetch('https://private-gold-dashboard.onrender.com/analyze_custom', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbol: selectedSymbol, mode: selectedMode })
            });
            const data = await res.json();
            setMessages(prev => [...prev, { role: 'bot', text: data.reply }]);
        } catch (err) {
            setMessages(prev => [...prev, { role: 'bot', text: '❌ เชื่อมต่อ Server ไม่ได้' }]);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-full bg-zinc-800 border border-yellow-500/30 rounded-2xl shadow-xl overflow-hidden">
            <div className="bg-zinc-900 p-4 border-b border-yellow-500/20 flex justify-between items-center">
                <div className="flex items-center gap-2">
                    <div className="bg-yellow-500/20 p-2 rounded-full"><FaRobot className="text-yellow-500" /></div>
                    <span className="font-bold text-white">AI Assistant</span>
                </div>
                <div className="text-xs text-green-500 flex items-center gap-1">● Online</div>
            </div>

            <div className="bg-zinc-800 p-3 border-b border-zinc-700 flex flex-col gap-2">
                <div className="flex gap-2">
                    <select
                        value={selectedSymbol}
                        onChange={(e) => setSelectedSymbol(e.target.value)}
                        className="flex-1 bg-zinc-900 text-white text-xs p-2 rounded border border-zinc-600 focus:border-yellow-500 outline-none"
                    >
                        <option value="GOLD">GOLD</option>
                        <option value="BITCOIN">BITCOIN</option>
                    </select>
                    <select
                        value={selectedMode}
                        onChange={(e) => setSelectedMode(e.target.value)}
                        className="flex-1 bg-zinc-900 text-white text-xs p-2 rounded border border-zinc-600 focus:border-yellow-500 outline-none"
                    >
                        <option value="scalping">🏎️ ซิ่ง (M15)</option>
                        <option value="daytrade">📅 วัน (H1)</option>
                        <option value="swing">💎 ยาว (D1)</option>
                    </select>
                </div>
                <button
                    onClick={requestAnalysis}
                    disabled={loading}
                    className="w-full bg-gradient-to-r from-yellow-600 to-yellow-500 text-zinc-900 text-xs font-bold py-2 rounded hover:from-yellow-500 hover:to-yellow-400 transition-all shadow-lg disabled:opacity-50"
                >
                    {loading ? 'กำลังวิเคราะห์...' : '🚀 ขอแผนเทรดเดี๋ยวนี้!'}
                </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar bg-zinc-800/50 min-h-[400px]">
                {messages.map((msg, i) => (
                    <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[90%] p-3 rounded-2xl text-sm whitespace-pre-line ${msg.role === 'user' ? 'bg-yellow-500 text-zinc-900 rounded-tr-none font-bold' : 'bg-zinc-700 text-white rounded-tl-none'}`}>
                            {msg.text}
                        </div>
                    </div>
                ))}
                {loading && <div className="flex justify-start"><div className="bg-zinc-700 p-2 rounded-2xl rounded-tl-none text-gray-400 text-xs animate-pulse">กำลังวางแผนเทรด...</div></div>}
                <div ref={messagesEndRef} />
            </div>

            <form onSubmit={sendMessage} className="p-3 bg-zinc-900 border-t border-zinc-700 flex gap-2">
                <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="พิมพ์ถามเองได้..."
                    className="flex-1 bg-zinc-800 text-white text-sm px-4 py-2 rounded-full focus:outline-none focus:ring-1 focus:ring-yellow-500"
                />
                <button type="submit" disabled={loading} className="bg-yellow-500 text-zinc-900 p-2 rounded-full hover:bg-yellow-400 transition-colors">
                    <FaPaperPlane className="text-sm" />
                </button>
            </form>
        </div>
    );
}