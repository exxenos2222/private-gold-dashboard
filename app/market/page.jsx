'use client'
import { useEffect, useState, useCallback } from 'react'
import { FaChartLine, FaRegNewspaper, FaSyncAlt, FaTimes, FaArrowUp, FaArrowDown, FaExclamationTriangle } from 'react-icons/fa';
import { MdOutlineDateRange, MdAccessTime } from 'react-icons/md';
import ChatPanel from '../components/ChatPanel';

const ChartButton = ({ symbol, currentSymbol, onClick, label }) => (
    <button
        onClick={() => onClick(symbol)}
        className={`px-3 py-1 rounded-lg text-sm font-bold transition-all duration-200 
            ${currentSymbol === symbol
                ? "bg-yellow-500 text-zinc-900 shadow-md shadow-yellow-500/50"
                : "bg-zinc-700 text-gray-300 hover:bg-zinc-600"
            }`}
    >
        {label}
    </button>
);

const ImpactPill = ({ impact }) => {
    let colorClass;
    let text;
    switch ((impact || "").toLowerCase()) {
        case "high": colorClass = "bg-red-500 text-white"; text = "สูง"; break;
        case "medium": colorClass = "bg-amber-500 text-zinc-900"; text = "กลาง"; break;
        case "low": colorClass = "bg-yellow-500 text-zinc-900"; text = "ต่ำ"; break;
        default: colorClass = "bg-gray-500 text-white"; text = "N/A";
    }
    return <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${colorClass}`}>{text}</span>;
};

export default function MarketPage() {
    const [news, setNews] = useState([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')
    const [filter, setFilter] = useState('all')
    const [currentSymbol, setCurrentSymbol] = useState("OANDA:XAUUSD")
    const [mainTicker, setMainTicker] = useState({ price: 'Loading...', change: 0, percent: 0 });
    const [watchlist, setWatchlist] = useState([]);
    const [countdown, setCountdown] = useState({ minutes: 0, time: '' });
    const [aiData, setAiData] = useState(null);

    const FF_JSON = 'https://nfs.faireconomy.media/ff_calendar_thisweek.json'
    const ALL_ORIGINS_GET = 'https://api.allorigins.win/get?url='
    const todayStr = new Date().toISOString().slice(0, 10);

    const generateMockData = useCallback(() => {
        const mockWatchlist = [
            { symbol: 'BINANCE:BTCUSDT', price: (Math.random() * (70000 - 60000) + 60000).toFixed(0), change: (Math.random() * 1000 - 500).toFixed(0), signal: Math.random() > 0.7 ? 'Sell' : Math.random() < 0.3 ? 'Buy' : 'Hold' },
            { symbol: 'OANDA:EURUSD', price: (Math.random() * (1.09 - 1.05) + 1.05).toFixed(4), change: (Math.random() * 0.01 - 0.005).toFixed(4), signal: Math.random() > 0.6 ? 'Buy' : 'Hold' },
        ];
        setWatchlist(mockWatchlist);
    }, []);

    const checkNextHighImpactNews = useCallback((events) => {
        const now = new Date();
        let nextHighImpact = null;
        const highImpactEvents = events.filter(ev => (ev.impact || "").toLowerCase() === 'high' && ev.__normDate === todayStr);
        for (const ev of highImpactEvents) {
            const [h, m] = (ev.time || '00:00').split(':').map(Number);
            const eventDate = new Date(`${ev.__normDate}T${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:00`);
            if (eventDate > now) {
                if (!nextHighImpact || eventDate < nextHighImpact.date) {
                    nextHighImpact = { date: eventDate, title: ev.title, time: ev.time };
                }
            }
        }
        if (nextHighImpact) {
            const diffMs = nextHighImpact.date - now;
            setCountdown({ minutes: Math.ceil(diffMs / (1000 * 60)), time: nextHighImpact.time });
        } else {
            setCountdown({ minutes: -1, time: 'N/A' });
        }
    }, [todayStr]);

    const normalizeEventDateToYYYYMMDD = (rawDate) => {
        if (!rawDate) return null;
        if (/^\d{4}-\d{2}-\d{2}$/.test(rawDate)) return rawDate;
        const m = rawDate.match(/^([A-Za-z]{3})\s+(\d{1,2})$/);
        if (m) {
            const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
            const monIndex = monthNames.indexOf(m[1]);
            if (monIndex !== -1) {
                const currentYear = new Date().getFullYear();
                return `${currentYear}-${String(monIndex + 1).padStart(2, '0')}-${String(m[2]).padStart(2, '0')}`;
            }
        }
        const parsed = new Date(rawDate);
        if (!isNaN(parsed)) return `${parsed.getFullYear()}-${String(parsed.getMonth() + 1).padStart(2, '0')}-${String(parsed.getDate()).padStart(2, '0')}`;
        return null;
    }

    const fetchNews = useCallback(async (currentFilter = filter) => {
        setLoading(true); setError(''); setNews([]);
        try {
            const res = await fetch(ALL_ORIGINS_GET + encodeURIComponent(FF_JSON))
            if (!res.ok) throw new Error('Network response was not ok');
            const wrapper = await res.json()
            const events = JSON.parse(wrapper.contents)
            const normalized = events.map(ev => ({ ...ev, __normDate: normalizeEventDateToYYYYMMDD(ev.date) }))
            checkNextHighImpactNews(normalized);
            let todayEvents = normalized.filter(ev => ev.__normDate === todayStr)
            if (currentFilter !== "all") todayEvents = todayEvents.filter(ev => (ev.impact || "").toLowerCase() === currentFilter.toLowerCase())
            setNews(todayEvents.sort((a, b) => (a.time < b.time ? -1 : 1)))
        } catch (err) {
            console.error("Fetch News Error:", err);
            // ไม่ต้อง Set Error ให้หน้าเว็บพัง แค่ Log บอก
        } finally { setLoading(false) }
    }, [checkNextHighImpactNews, todayStr, filter]);

    const loadChart = useCallback((symbol) => {
        const container = document.getElementById("tradingview_chart")
        if (!container) return
        container.innerHTML = ""
        if (window.TradingView && window.TradingView.widget) {
            new window.TradingView.widget({
                width: "100%",
                height: 950,
                symbol,
                interval: "5",
                timezone: "Asia/Bangkok",
                theme: "dark",
                style: "1",
                locale: "th",
                container_id: "tradingview_chart",
                enable_publishing: false,
                withdateranges: true,
                drawings_access: { type: 'black', tools: [{ name: "FibRetracement", type: "drawing" }, { name: "Rectangle", type: "drawing" }] },
                left_toolbar: true,
                studies: [{ id: "MASimple@tv-basicstudies", type: "EMA", inputs: { length: 50 } }, { id: "RSI@tv-basicstudies", type: "RSI", inputs: { length: 14 } }],
            })
        }
    }, [])

    const switchChart = (symbol) => setCurrentSymbol(symbol)

    // --- useEffects ---
    useEffect(() => { const intervalId = setInterval(generateMockData, 5000); return () => clearInterval(intervalId); }, [generateMockData]);
    useEffect(() => {
        const fetchAI = async () => {
            try {
                const res = await fetch('https://private-gold-dashboard.onrender.com/analyze/GC=F');
                if (!res.ok) throw new Error('Connect failed');
                const data = await res.json();
                setAiData(data);
                setMainTicker({ price: data.price, change: data.change, percent: data.percent });
            } catch (err) { console.log("AI Backend not connected"); }
        };
        fetchAI();
        const aiInterval = setInterval(fetchAI, 5000);
        return () => clearInterval(aiInterval);
    }, []);
    useEffect(() => {
        const script = document.createElement('script')
        script.src = 'https://s3.tradingview.com/tv.js'
        script.async = true
        document.body.appendChild(script)
        script.onload = () => setTimeout(() => loadChart(currentSymbol), 500);
        return () => document.body.removeChild(script);
    }, [loadChart, currentSymbol])
    useEffect(() => {
        const timerId = setInterval(() => {
            if (countdown.minutes > 0) setCountdown(prev => ({ ...prev, minutes: prev.minutes - 1 }));
            if (countdown.minutes === 0) fetchNews();
        }, 60000);
        return () => clearInterval(timerId);
    }, [countdown.minutes, fetchNews]);
    useEffect(() => { fetchNews(); }, [fetchNews]);

    // --- Components ---
    const TickerBar = () => {
        const isPositive = mainTicker.change > 0;
        const colorClass = isPositive ? 'text-green-400' : mainTicker.change < 0 ? 'text-red-400' : 'text-gray-400';
        const Icon = isPositive ? FaArrowUp : mainTicker.change < 0 ? FaArrowDown : FaTimes;
        return (
            <div className="flex items-center gap-4 bg-zinc-800/90 border-b border-yellow-500/30 py-2 px-4 sticky top-0 z-20 backdrop-blur-sm">
                <div className="flex items-center text-sm font-bold text-white">
                    <span className="text-yellow-500 mr-2">XAUUSD:</span>
                    <span className={`mr-2 ${colorClass}`}>{mainTicker.price}</span>
                    <span className={`${colorClass} flex items-center`}><Icon className="w-3 h-3 mr-1" />{mainTicker.change > 0 ? '+' : ''}{mainTicker.change} ({mainTicker.percent > 0 ? '+' : ''}{mainTicker.percent}%)</span>
                </div>
                <div className="flex items-center text-sm font-semibold">
                    {countdown.minutes > 0 ? <span className="text-red-400 flex items-center gap-1 bg-red-900/40 px-2 py-1 rounded-full"><MdAccessTime className="w-4 h-4" /> ข่าว High Impact ใน: {countdown.minutes} นาที ({countdown.time})</span> : countdown.minutes === 0 ? <span className="text-red-400 flex items-center gap-1 bg-red-900/40 px-2 py-1 rounded-full animate-pulse"><FaExclamationTriangle className="w-4 h-4" /> ข่าวสำคัญกำลังจะออก!</span> : <span className="text-gray-500 flex items-center gap-1 px-2 py-1 rounded-full"><MdAccessTime className="w-4 h-4" /> ไม่มีข่าว High Impact ที่จะถึงวันนี้</span>}
                </div>
            </div>
        );
    };

    const formatDateTime = (dateStr, timeStr) => {
        if (!dateStr) return "";
        const date = new Date(dateStr);
        const formattedDate = `${String(date.getDate()).padStart(2, '0')}/${String(date.getMonth() + 1).padStart(2, '0')}`;

        // Convert 12h to 24h if needed
        let time = timeStr || '';
        if (time && (time.toLowerCase().includes('am') || time.toLowerCase().includes('pm'))) {
            const [timePart, modifier] = time.split(' ');
            let [hours, minutes] = timePart.split(':');
            if (hours === '12') {
                hours = '00';
            }
            if (modifier.toLowerCase() === 'pm') {
                hours = parseInt(hours, 10) + 12;
            }
            time = `${hours}:${minutes}`;
        }

        return `${formattedDate} ${time}`.trim();
    };

    return (
        <main className="min-h-screen w-full pb-16 text-white bg-zinc-900 font-sans overflow-x-hidden">
            <TickerBar />

            <div className="max-w-[1920px] mx-auto px-4 pt-6">
                <header className="flex flex-col sm:flex-row items-center justify-between mb-6">
                    <div className="flex items-center gap-3 mb-4 sm:mb-0">
                        <div className="w-10 h-10 rounded-full grid place-items-center bg-yellow-500 text-zinc-900 font-extrabold text-lg shadow-lg">PG</div>
                        <h1 className="text-2xl md:text-3xl font-extrabold tracking-wider text-white">Private<span className="text-yellow-500">Gold</span></h1>
                    </div>
                    <div className="flex gap-3">
                        <a className="flex items-center gap-1 px-3 py-1.5 rounded-full bg-yellow-500 text-zinc-900 text-xs font-bold hover:bg-yellow-400" href="https://www.goldtraders.or.th/" target="_blank"><MdOutlineDateRange /> ราคาทองวันนี้</a>
                        <a className="flex items-center gap-1 px-3 py-1.5 rounded-full bg-zinc-700 text-white text-xs font-bold hover:bg-zinc-600" href="https://finviz.com/forex.ashx" target="_blank">FINVIZ</a>
                    </div>
                </header>

                <div className="grid grid-cols-1 xl:grid-cols-4 gap-6 items-start">

                    <div className="xl:col-span-3 flex flex-col gap-6">
                        <section className="bg-zinc-800/80 backdrop-blur-sm rounded-xl shadow-2xl p-4 border border-zinc-700">
                            <div className="flex items-center justify-between mb-2">
                                <h2 className="text-lg font-bold flex items-center gap-2 text-yellow-500"><FaChartLine /> Real-time Chart</h2>
                                <div className="flex gap-2">
                                    <ChartButton symbol="OANDA:XAUUSD" currentSymbol={currentSymbol} onClick={switchChart} label="GOLD" />
                                    <ChartButton symbol="BINANCE:BTCUSDT" currentSymbol={currentSymbol} onClick={switchChart} label="BTC" />
                                </div>
                            </div>
                            <div id="tradingview_chart" className="rounded-lg overflow-hidden border border-zinc-600" style={{ minHeight: '950px' }} />
                        </section>

                        <section className="bg-zinc-800/80 backdrop-blur-sm rounded-xl shadow-2xl p-4 border border-zinc-700">
                            <div className="flex items-center justify-between border-b border-yellow-500/20 pb-3 mb-3">
                                <h2 className="text-lg font-bold flex items-center gap-2 text-yellow-500"><FaRegNewspaper /> ข่าววันนี้</h2>
                                <div className="flex gap-2">
                                    <select value={filter} onChange={e => { setFilter(e.target.value); fetchNews(e.target.value); }} className="bg-zinc-700 px-2 py-1 rounded text-xs"><option value="all">All</option><option value="high">High Impact</option></select>
                                    <button onClick={() => fetchNews(filter)} className="px-3 py-1 bg-yellow-500 text-zinc-900 rounded text-xs font-bold hover:bg-yellow-400"><FaSyncAlt /></button>
                                </div>
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                {news.map((n, i) => (
                                    <div key={i} className={`p-3 rounded-lg border-l-4 ${n.impact === "High" ? "bg-red-900/40 border-red-500" : "bg-zinc-700 border-gray-500"} shadow`}>
                                        <div className="flex justify-between mb-1">
                                            <ImpactPill impact={n.impact} />
                                            <span className="text-xs text-gray-400 font-mono">{formatDateTime(n.__normDate, n.time)}</span>
                                        </div>
                                        <a href={`https://www.google.com/search?q=${encodeURIComponent(n.title)}`} target="_blank" rel="noopener noreferrer" className="text-sm font-semibold text-white hover:text-yellow-500 hover:underline block">
                                            {n.title}
                                        </a>
                                    </div>
                                ))}
                            </div>
                        </section>
                    </div>

                    <div className="xl:col-span-1 flex flex-col gap-6 sticky top-4">
                        <div className="h-[600px]">
                            <ChatPanel />
                        </div>

                        <section className="bg-zinc-800/80 backdrop-blur-sm rounded-xl shadow-2xl p-4 border border-zinc-700">
                            <h2 className="text-lg font-bold flex items-center gap-2 text-yellow-500 mb-3"><FaChartLine /> Watchlist</h2>
                            <div className="space-y-2">
                                {aiData && (
                                    <div className="p-3 bg-gradient-to-r from-zinc-900 to-zinc-800 border border-yellow-500/50 rounded-lg">
                                        <div className="flex justify-between items-center mb-1">
                                            <span className="text-yellow-500 font-bold text-xs">AI SCANNER</span>
                                            <span className={`px-2 py-0.5 text-[10px] font-bold rounded ${(aiData.trend || "").includes('UP') ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                                                {aiData.trend || "WAIT"}
                                            </span>
                                        </div>
                                        <div className="flex justify-between items-end">
                                            <span className="text-lg font-bold text-white">{aiData.symbol}</span>
                                            <span className="text-sm text-gray-400">${aiData.price}</span>
                                        </div>
                                    </div>
                                )}
                                {watchlist.map(item => (
                                    <div key={item.symbol} className="flex justify-between items-center bg-zinc-700 p-3 rounded-lg">
                                        <span className="font-bold text-white text-sm">{item.symbol.split(':')[1] || item.symbol}</span>
                                        <span className={`text-sm font-semibold ${item.change > 0 ? 'text-green-400' : 'text-red-400'}`}>{item.price}</span>
                                    </div>
                                ))}
                            </div>
                        </section>

                    </div>
                </div>
            </div>
        </main>
    )
}