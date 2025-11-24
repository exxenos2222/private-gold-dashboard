
'use client'
import { useEffect, useState, useCallback } from 'react'
import { FaChartLine, FaRegNewspaper, FaSyncAlt, FaTimes, FaArrowUp, FaArrowDown, FaExclamationTriangle, FaRobot } from 'react-icons/fa';
import { MdOutlineDateRange, MdAccessTime } from 'react-icons/md';
import ChatWidget from '../components/ChatWidget'; 

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
        case "high":
            colorClass = "bg-red-500 text-white";
            text = "สูง";
            break;
        case "medium":
            colorClass = "bg-amber-500 text-zinc-900";
            text = "กลาง";
            break;
        case "low":
            colorClass = "bg-yellow-500 text-zinc-900";
            text = "ต่ำ";
            break;
        default:
            colorClass = "bg-gray-500 text-white";
            text = "N/A";
    }
    return (
        <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${colorClass}`}>
            {text}
        </span>
    );
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

        const highImpactEvents = events.filter(ev => 
            (ev.impact || "").toLowerCase() === 'high' && ev.__normDate === todayStr
        );

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
            const minutes = Math.ceil(diffMs / (1000 * 60));
            setCountdown({ minutes, time: nextHighImpact.time });
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
        if (!isNaN(parsed)) {
            return `${parsed.getFullYear()}-${String(parsed.getMonth() + 1).padStart(2, '0')}-${String(parsed.getDate()).padStart(2, '0')}`;
        }
        return null;
    }

    const fetchNews = useCallback(async (currentFilter = filter) => {
        setLoading(true)
        setError('')
        setNews([])

        try {
            const res = await fetch(ALL_ORIGINS_GET + encodeURIComponent(FF_JSON))
            const wrapper = await res.json()
            const events = JSON.parse(wrapper.contents)

            const normalized = events.map(ev => ({
                ...ev,
                __normDate: normalizeEventDateToYYYYMMDD(ev.date)
            }))
            
            checkNextHighImpactNews(normalized);

            let todayEvents = normalized.filter(ev => ev.__normDate === todayStr)

            if (currentFilter !== "all") {
                todayEvents = todayEvents.filter(ev =>
                    (ev.impact || "").toLowerCase() === currentFilter.toLowerCase()
                )
            }

            setNews(todayEvents.sort((a, b) => {
                if (a.time < b.time) return -1;
                if (a.time > b.time) return 1;
                return 0;
            }))
        } catch (err) {
            console.error("Fetch News Error:", err);
            setError("ไม่สามารถดึงรายการข่าวได้ โปรดลองอีกครั้ง");
        } finally {
            setLoading(false)
        }
    }, [checkNextHighImpactNews, todayStr, filter]);
    
    const loadChart = useCallback((symbol) => {
        const container = document.getElementById("tradingview_chart")
        if (!container) return
        container.innerHTML = ""

        if (window.TradingView && window.TradingView.widget) {
            new window.TradingView.widget({
                width: "100%",
                height: 800, 
                symbol,
                interval: "5", 
                timezone: "Asia/Bangkok",
                theme: "dark",
                style: "1",
                locale: "th",
                container_id: "tradingview_chart",
                enable_publishing: false,
                withdateranges: true,
                drawings_access: {
                    type: 'black',
                    tools: [
                        { name: "FibRetracement", type: "drawing" },
                        { name: "Rectangle", type: "drawing" },
                    ],
                },
                left_toolbar: false, 
                studies: [
                    {
                        id: "MASimple@tv-basicstudies", 
                        type: "EMA",
                        inputs: { length: 50 },
                    },
                    {
                        id: "RSI@tv-basicstudies", 
                        type: "RSI",
                        inputs: { length: 14 },
                    },
                ],
            })
        }
    }, []) 

    const switchChart = (symbol) => {
        setCurrentSymbol(symbol)
    }
    
    useEffect(() => {
        const intervalId = setInterval(generateMockData, 5000); 
        return () => clearInterval(intervalId);
    }, [generateMockData]);

    useEffect(() => {
        const fetchAI = async () => {
            try {
                const res = await fetch('https://private-gold-dashboard.onrender.com/analyze/GC=F');
                if (!res.ok) { throw new Error('Connect failed'); }
                const data = await res.json();
                
                setAiData(data);

                setMainTicker({
                    price: data.price,
                    change: data.change, 
                    percent: data.percent
                });
            } catch (err) {
                console.log("AI Backend not connected (Optional):", err);
            }
        };

        fetchAI();
        const aiInterval = setInterval(fetchAI, 60000); 

        return () => clearInterval(aiInterval);
    }, []);

    useEffect(() => {
        const script = document.createElement('script')
        script.src = 'https://s3.tradingview.com/tv.js'
        script.async = true
        document.body.appendChild(script)
        
        script.onload = () => {
            setTimeout(() => {
                loadChart(currentSymbol);
            }, 500); 
        };

        return () => {
            document.body.removeChild(script);
        };
    }, [loadChart, currentSymbol]) 
    
    useEffect(() => {
        const timerId = setInterval(() => {
            if (countdown.minutes > 0) {
                setCountdown(prev => ({ ...prev, minutes: prev.minutes - 1 }));
            }
            if (countdown.minutes === 0) {
                 fetchNews();
            }
        }, 60000); 
        
        return () => clearInterval(timerId);
    }, [countdown.minutes, fetchNews]); 

    useEffect(() => {
        fetchNews();
    }, [fetchNews]); 

    const TickerBar = () => {
        const isPositive = mainTicker.change > 0;
        const colorClass = isPositive ? 'text-green-400' : mainTicker.change < 0 ? 'text-red-400' : 'text-gray-400';
        const Icon = isPositive ? FaArrowUp : mainTicker.change < 0 ? FaArrowDown : FaTimes;

        return (
            <div className="flex items-center gap-4 bg-zinc-800/90 border-b border-yellow-500/30 py-2 px-4 sticky top-0 z-10 backdrop-blur-sm">
                <div className="flex items-center text-sm font-bold text-white">
                    <span className="text-yellow-500 mr-2">XAUUSD:</span>
                    <span className={`mr-2 ${colorClass}`}>{mainTicker.price}</span>
                    <span className={`${colorClass} flex items-center`}>
                        <Icon className="w-3 h-3 mr-1" />
                        {mainTicker.change > 0 ? '+' : ''}{mainTicker.change} ({mainTicker.percent > 0 ? '+' : ''}{mainTicker.percent}%)
                    </span>
                </div>
                
                <div className="flex items-center text-sm font-semibold">
                    {countdown.minutes > 0 ? (
                        <span className="text-red-400 flex items-center gap-1 bg-red-900/40 px-2 py-1 rounded-full">
                            <MdAccessTime className="w-4 h-4" />
                            ข่าว High Impact ใน: {countdown.minutes} นาที ({countdown.time})
                        </span>
                    ) : countdown.minutes === 0 ? (
                         <span className="text-red-400 flex items-center gap-1 bg-red-900/40 px-2 py-1 rounded-full animate-pulse">
                            <FaExclamationTriangle className="w-4 h-4" /> ข่าวสำคัญกำลังจะออก!
                        </span>
                    ) : (
                         <span className="text-gray-500 flex items-center gap-1 px-2 py-1 rounded-full">
                            <MdAccessTime className="w-4 h-4" />
                            ไม่มีข่าว High Impact ที่จะถึงวันนี้
                        </span>
                    )}
                </div>
            </div>
        );
    };

    const WatchlistSection = () => (
        <section className="bg-zinc-800/80 backdrop-blur-sm rounded-xl shadow-2xl p-5 border border-zinc-700">
            <h2 className="text-xl font-bold flex items-center gap-2 text-yellow-500 mb-4 border-b border-zinc-700 pb-3">
                <FaChartLine className="w-5 h-5" /> Watchlist & สัญญาณสแกน
            </h2>
            <div className="space-y-3">
                {/* AI Widget */}
                {aiData ? (
                    <div className="mb-4 p-4 bg-gradient-to-r from-zinc-900 to-zinc-800 border border-yellow-500/50 rounded-lg flex items-center justify-between shadow-lg shadow-yellow-500/10">
                        <div className="flex items-center gap-3">
                            <div className="p-3 bg-yellow-500/20 rounded-full text-yellow-400 text-xl animate-bounce-slow">
                                <FaRobot />
                            </div>
                            <div>
                                <h3 className="text-yellow-500 font-bold text-xs uppercase tracking-wider">AI Prediction (Python)</h3>
                                <div className="flex items-baseline gap-2">
                                    <span className="text-lg font-bold text-white">{aiData.symbol}</span>
                                    <span className="text-sm text-gray-400">${aiData.price}</span>
                                </div>
                            </div>
                        </div>
                        <div className="text-right">
                             <div className={`px-3 py-1 text-sm font-bold rounded uppercase ${
                                (aiData.trend || "").includes('UP') ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                             }`}>
                                {aiData.trend}
                            </div>
                            <div className="text-[10px] text-gray-500 mt-1">Trend 5 วันล่าสุด</div>
                        </div>
                    </div>
                ) : (
                    <div className="mb-4 p-3 bg-zinc-800/50 border border-dashed border-zinc-600 rounded text-center text-zinc-500 text-sm">
                        ⏳ กำลังเชื่อมต่อสมอง AI... (รัน python ยัง?)
                    </div>
                )}

                {watchlist.map(item => {
                    const isPositive = item.change > 0;
                    const colorClass = isPositive ? 'text-green-400' : item.change < 0 ? 'text-red-400' : 'text-gray-400';
                    const signalColor = item.signal === 'Buy' ? 'bg-green-600' : item.signal === 'Sell' ? 'bg-red-600' : 'bg-gray-600';
                    
                    return (
                        <div key={item.symbol} className="flex justify-between items-center bg-zinc-700 p-3 rounded-lg hover:bg-zinc-600 transition-colors cursor-pointer">
                            <div className="flex items-center gap-2">
                                <span className="font-bold text-white">{item.symbol.split(':')[1] || item.symbol}</span>
                                <span className={`px-2 py-0.5 text-xs font-semibold rounded-full ${signalColor} text-white`}>
                                    {item.signal}
                                </span>
                            </div>
                            <div className="text-right">
                                <span className={`text-sm font-semibold ${colorClass}`}>{item.price}</span>
                            </div>
                        </div>
                    );
                })}
            </div>
        </section>
    );

    return (
        <main className="min-h-screen max-w-[1600px] mx-auto pb-16 text-white bg-zinc-900 font-sans">
            
            <TickerBar />

            <div className="px-4"> 
                
                <header className="flex flex-col sm:flex-row items-center justify-between py-6 border-b border-yellow-500/20 mb-6">
                    <div className="flex items-center gap-3 mb-4 sm:mb-0">
                        <div className="w-12 h-12 rounded-full grid place-items-center bg-yellow-500 text-zinc-900 font-extrabold text-xl shadow-lg shadow-yellow-500/40">
                            PG
                        </div>
                        <h1 className="text-3xl md:text-4xl font-extrabold tracking-wider text-white">Private<span className="text-yellow-500">Gold</span></h1>
                    </div>

                    <div className="flex flex-wrap justify-center gap-3">
                        <a className="flex items-center gap-1 px-4 py-2 rounded-full bg-yellow-500 text-zinc-900 text-sm font-bold hover:bg-yellow-400 transition-colors shadow-md hover:shadow-lg"
                            href="https://www.goldtraders.or.th/" target="_blank" rel="noopener noreferrer">
                            <MdOutlineDateRange className="w-4 h-4" /> ราคาทองวันนี้
                        </a>
                        <a className="flex items-center gap-1 px-4 py-2 rounded-full bg-zinc-700 text-white text-sm font-bold hover:bg-zinc-600 transition-colors shadow-md"
                            href="https://finviz.com/forex.ashx" target="_blank" rel="noopener noreferrer">
                            FINVIZ
                        </a>
                    </div>
                </header>

                <div className="grid grid-cols-1 gap-8"> 
                    <div className="flex flex-col gap-8">

                        <WatchlistSection />
                        
                        <section className="bg-zinc-800/80 backdrop-blur-sm rounded-xl shadow-2xl p-5 border border-zinc-700">
                            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-4">
                                <h2 className="text-xl font-bold flex items-center gap-2 text-yellow-500 mb-2 sm:mb-0">
                                    <FaChartLine className="w-5 h-5" /> กราฟราคาแบบเรียลไทม์
                                </h2>
                                <div className="flex gap-2">
                                    <ChartButton symbol="OANDA:XAUUSD" currentSymbol={currentSymbol} onClick={switchChart} label="XAUUSD (GOLD)" />
                                    <ChartButton symbol="BINANCE:BTCUSDT" currentSymbol={currentSymbol} onClick={switchChart} label="BTCUSDT (Crypto)" />
                                </div>
                            </div>
                            <div id="tradingview_chart" className="rounded-lg overflow-hidden border border-zinc-600 shadow-inner" style={{ minHeight: '800px' }} />
                        </section>

                        <section className="bg-zinc-800/80 backdrop-blur-sm rounded-xl shadow-2xl p-5 border border-zinc-700">
                            <div className="flex flex-col md:flex-row items-start md:items-center justify-between border-b border-yellow-500/20 pb-4 mb-4">
                                <h2 className="text-xl font-bold flex items-center gap-2 text-yellow-500 mb-3 md:mb-0">
                                    <FaRegNewspaper className="w-5 h-5" /> ปฏิทินข่าววันนี้ ({todayStr})
                                </h2>
                                <div className="flex flex-wrap items-center gap-3">
                                    <select value={filter} onChange={e => { setFilter(e.target.value); fetchNews(e.target.value); }}
                                        className="bg-zinc-700 px-3 py-2 rounded-lg text-sm appearance-none focus:ring-1 focus:ring-yellow-500 transition-colors cursor-pointer">
                                        <option value="all">Impact: ทั้งหมด</option>
                                        <option value="low">Impact: ต่ำ</option>
                                        <option value="medium">Impact: กลาง</option>
                                        <option value="high">Impact: สูง</option>
                                    </select>
                                    <button onClick={() => fetchNews(filter)} disabled={loading}
                                        className={`flex items-center gap-1 px-4 py-2 rounded-xl text-sm font-bold transition-all duration-300 ${loading ? "bg-zinc-600 text-gray-400 cursor-not-allowed" : "bg-yellow-500 text-zinc-900 hover:bg-yellow-400 shadow-md"}`}>
                                        <FaSyncAlt className={loading ? "animate-spin" : ""} />
                                        {loading ? "กำลังโหลด..." : "อัปเดตข่าว"}
                                    </button>
                                    <button onClick={() => { setNews([]); setError(""); }} className="flex items-center gap-1 px-4 py-2 rounded-xl bg-zinc-700 text-sm hover:bg-zinc-600 transition-colors">
                                        <FaTimes /> ล้างข่าว
                                    </button>
                                </div>
                            </div>

                            {loading && <p className="text-center py-4 text-gray-400 flex items-center justify-center gap-2"><FaSyncAlt className="animate-spin" /> กำลังโหลดข่าวสาร...</p>}
                            {error && <p className="text-center py-4 text-red-400 font-medium">{error}</p>}
                            {!loading && !error && news.length === 0 && (
                                <p className="text-center py-4 text-gray-500">✅ ไม่มีข่าวเศรษฐกิจที่ต้องจับตามองในวันนี้</p>
                            )}

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {news.map((n, i) => (
                                    <div key={i} className={`p-4 rounded-xl border-l-4 transition-all duration-300 ${n.impact === "High" ? "bg-red-900/40 border-red-500 hover:bg-red-900/60" : n.impact === "Medium" ? "bg-amber-900/40 border-amber-500 hover:bg-amber-900/60" : "bg-yellow-900/30 border-yellow-500 hover:bg-yellow-900/50"} shadow-lg`}>
                                        <div className="flex items-center justify-between mb-2">
                                            <ImpactPill impact={n.impact} />
                                            <p className="text-sm font-medium text-white/80">{n.time || n.date}</p>
                                        </div>
                                        <h3 className="font-semibold text-white text-base mb-2">{n.title}</h3>
                                        <div className='flex justify-between items-end mt-3'>
                                            <span className='text-xs font-light text-white/60'>{n.country} | Actual: {n.actual || '-'}</span>
                                            <a className='text-sm font-medium text-yellow-400 hover:text-yellow-300 underline transition-colors' href='https://www.forexfactory.com/calendar' target='_blank' rel="noopener noreferrer">ดูรายละเอียด »</a>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </section>
                    </div>
                </div>
            </div>
            <ChatWidget />
        </main>
    )
}