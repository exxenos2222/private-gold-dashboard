'use client'
import { useState, useRef, useEffect } from 'react'
import { FaRobot, FaPaperPlane, FaTimes, FaCommentDots } from 'react-icons/fa';

export default function ChatWidget() {
    const [isOpen, setIsOpen] = useState(false);
    const [messages, setMessages] = useState([
        { role: 'bot', text: 'สวัสดีครับ 👋 ผม AI PrivateGold ถามราคาทองหรือกราฟได้เลยครับ!' }
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

        const userMsg = input;
        setMessages(prev => [...prev, { role: 'user', text: userMsg }]);
        setInput('');
        setLoading(true);

        try {
            const res = await fetch('https://private-gold-dashboard.onrender.com/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: userMsg })
            });
            const data = await res.json();
            setMessages(prev => [...prev, { role: 'bot', text: data.reply }]);
        } catch (err) {
            setMessages(prev => [...prev, { role: 'bot', text: '❌ ขอโทษครับ ติดต่อ Server ไม่ได้ (Server อาจจะหลับอยู่ รอสักครู่)' }]);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end font-sans">
            {isOpen && (
                <div className="mb-4 w-80 h-96 bg-zinc-800 border border-yellow-500/30 rounded-2xl shadow-2xl flex flex-col overflow-hidden animate-in fade-in slide-in-from-bottom-10 duration-300">
                    <div className="bg-zinc-900 p-4 flex justify-between items-center border-b border-yellow-500/20">
                        <div className="flex items-center gap-2">
                            <div className="bg-yellow-500/20 p-2 rounded-full"><FaRobot className="text-yellow-500" /></div>
                            <span className="font-bold text-white">AI Assistant</span>
                        </div>
                        <button onClick={() => setIsOpen(false)} className="text-gray-400 hover:text-white"><FaTimes /></button>
                    </div>
                    <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
                        {messages.map((msg, i) => (
                            <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                <div className={`max-w-[80%] p-3 rounded-2xl text-sm ${msg.role === 'user' ? 'bg-yellow-500 text-zinc-900 rounded-tr-none font-semibold' : 'bg-zinc-700 text-white rounded-tl-none'}`}>
                                    {msg.text}
                                </div>
                            </div>
                        ))}
                        {loading && <div className="flex justify-start"><div className="bg-zinc-700 p-3 rounded-2xl rounded-tl-none text-gray-400 text-xs">AI กำลังพิมพ์...</div></div>}
                        <div ref={messagesEndRef} />
                    </div>
                    <form onSubmit={sendMessage} className="p-3 bg-zinc-900 border-t border-zinc-700 flex gap-2">
                        <input type="text" value={input} onChange={(e) => setInput(e.target.value)} placeholder="ถามราคาทอง..." className="flex-1 bg-zinc-800 text-white text-sm px-4 py-2 rounded-full focus:outline-none focus:ring-1 focus:ring-yellow-500" />
                        <button type="submit" disabled={loading} className="bg-yellow-500 text-zinc-900 p-2 rounded-full hover:bg-yellow-400 transition-colors"><FaPaperPlane className="text-sm" /></button>
                    </form>
                </div>
            )}
            <button onClick={() => setIsOpen(!isOpen)} className="w-14 h-14 bg-yellow-500 rounded-full shadow-lg shadow-yellow-500/40 flex items-center justify-center text-zinc-900 hover:scale-110 transition-transform duration-200">
                {isOpen ? <FaTimes className="text-2xl" /> : <FaCommentDots className="text-2xl" />}
            </button>
        </div>
    );
}