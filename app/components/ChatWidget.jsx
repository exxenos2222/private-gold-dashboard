'use client'
import { useState, useRef, useEffect } from 'react'
import { FaRobot, FaPaperPlane, FaTimes, FaCommentDots, FaCog } from 'react-icons/fa';

export default function ChatWidget() {
    const [isOpen, setIsOpen] = useState(false);
    
    // State สำหรับตัวเลือก
    const [selectedSymbol, setSelectedSymbol] = useState("GOLD");
    const [selectedMode, setSelectedMode] = useState("daytrade");

    const [messages, setMessages] = useState([
        { role: 'bot', text: 'สวัสดีครับ 👋 เลือกคู่เงินและโหมดด้านบน แล้วกดส่งเพื่อขอแผนเทรดได้เลย!' }
    ]);
    const [loading, setLoading] = useState(false);
    const messagesEndRef = useRef(null);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    // ฟังก์ชันส่งคำสั่งพิเศษ
    const requestAnalysis = async () => {
        setLoading(true);
        // เพิ่มข้อความฝั่งเรา
        const userText = `ขอแผน ${selectedSymbol} แบบ ${selectedMode}`;
        setMessages(prev => [...prev, { role: 'user', text: userText }]);

        try {
            // ยิงไปหา API ใหม่ที่เราเพิ่งสร้าง
            const res = await fetch('https://private-gold-dashboard.onrender.com/analyze_custom', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    symbol: selectedSymbol, 
                    mode: selectedMode 
                })
            });
            const data = await res.json();
            setMessages(prev => [...prev, { role: 'bot', text: data.reply }]);
        } catch (err) {
            setMessages(prev => [...prev, { role: 'bot', text: '❌ เชื่อมต่อ Server ไม่ได้ครับ' }]);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end font-sans">
            {isOpen && (
                <div className="mb-4 w-80 sm:w-96 bg-zinc-800 border border-yellow-500/30 rounded-2xl shadow-2xl flex flex-col overflow-hidden animate-in fade-in slide-in-from-bottom-10 duration-300">
                    
                    {/* Header สีดำ */}
                    <div className="bg-zinc-900 p-3 flex justify-between items-center border-b border-yellow-500/20">
                        <div className="flex items-center gap-2">
                            <div className="bg-yellow-500/20 p-1.5 rounded-full"><FaRobot className="text-yellow-500" /></div>
                            <span className="font-bold text-white text-sm">AI Trader Pro</span>
                        </div>
                        <button onClick={() => setIsOpen(false)} className="text-gray-400 hover:text-white"><FaTimes /></button>
                    </div>

                    {/* --- แผงควบคุม (Control Panel) --- */}
                    <div className="bg-zinc-800 p-3 border-b border-zinc-700 flex gap-2">
                        <select 
                            value={selectedSymbol}
                            onChange={(e) => setSelectedSymbol(e.target.value)}
                            className="flex-1 bg-zinc-900 text-white text-xs p-2 rounded border border-zinc-600 focus:border-yellow-500 outline-none"
                        >
                            <option value="GOLD">GOLD (ทองคำ)</option>
                            <option value="BITCOIN">BITCOIN</option>
                            <option value="EURUSD">EUR/USD</option>
                            <option value="GBPUSD">GBP/USD</option>
                            <option value="USDJPY">USD/JPY</option>
                        </select>

                        <select 
                            value={selectedMode}
                            onChange={(e) => setSelectedMode(e.target.value)}
                            className="flex-1 bg-zinc-900 text-white text-xs p-2 rounded border border-zinc-600 focus:border-yellow-500 outline-none"
                        >
                            <option value="scalping">🏎️ ซิ่ง (M15)</option>
                            <option value="daytrade">📅 จบในวัน (H1)</option>
                            <option value="swing">💎 ถือยาว (D1)</option>
                        </select>
                    </div>

                    <div className="h-80 overflow-y-auto p-4 space-y-4 custom-scrollbar bg-zinc-800/50">
                        {messages.map((msg, i) => (
                            <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                <div className={`max-w-[85%] p-3 rounded-2xl text-xs sm:text-sm whitespace-pre-line ${msg.role === 'user' ? 'bg-yellow-500 text-zinc-900 rounded-tr-none font-bold' : 'bg-zinc-700 text-white rounded-tl-none'}`}>
                                    {msg.text}
                                </div>
                            </div>
                        ))}
                        {loading && <div className="flex justify-start"><div className="bg-zinc-700 p-2 rounded-2xl rounded-tl-none text-gray-400 text-xs animate-pulse">กำลังวิเคราะห์กราฟ...</div></div>}
                        <div ref={messagesEndRef} />
                    </div>

                    <div className="p-3 bg-zinc-900 border-t border-zinc-700">
                        <button 
                            onClick={requestAnalysis} 
                            disabled={loading}
                            className="w-full bg-gradient-to-r from-yellow-600 to-yellow-500 text-zinc-900 font-bold py-2 rounded-lg hover:from-yellow-500 hover:to-yellow-400 transition-all shadow-lg disabled:opacity-50"
                        >
                            {loading ? 'กำลังคำนวณ...' : '🚀 ขอแผนเทรดเดี๋ยวนี้!'}
                        </button>
                    </div>
                </div>
            )}
            
            <button onClick={() => setIsOpen(!isOpen)} className="w-14 h-14 bg-yellow-500 rounded-full shadow-lg shadow-yellow-500/40 flex items-center justify-center text-zinc-900 hover:scale-110 transition-transform duration-200">
                {isOpen ? <FaTimes className="text-2xl" /> : <FaCog className="text-2xl" />}
            </button>
        </div>
    );
}