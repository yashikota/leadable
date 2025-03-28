import { useEffect, useState, useRef } from "react";
import { Link } from "react-router";
import { ArrowLeft } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { API_URL } from "../App";

// APIから返されるリソース情報の型
interface ResourceData {
  timestamp: number;
  cpu: {
    total: number;
    per_cpu: number[];
    memory: number;
  };
  gpu: {
    utilization: number;
    memory_used: number;
    memory_total: number;
  };
}

// グラフ表示のためのデータ型
interface ChartData {
  time: string;
  cpuTotal: number;
  memoryUsage: number;
  gpuUtilization: number;
  gpuMemoryUsage: number;
}

export function ResourceMonitor() {
  const [resourceData, setResourceData] = useState<ResourceData | null>(null);
  const [chartData, setChartData] = useState<ChartData[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isMonitoring, setIsMonitoring] = useState(true);

  // intervalのIDを保存するref
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  // コンポーネントのマウント時にリソース情報の取得を開始
  useEffect(() => {
    // リソース情報を取得する関数
    const fetchResourceData = async () => {
      try {
        const response = await fetch(`${API_URL}/resource`);

        // エラーヘッダーのチェック
        const errorMessage = response.headers.get("X-LEADABLE-ERROR-MESSAGE");
        if (errorMessage) {
          throw new Error(errorMessage);
        }

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data: ResourceData = await response.json();
        setResourceData(data);

        // 現在時刻をフォーマット (HH:MM:SS)
        const now = new Date();
        const timeString = now.toLocaleTimeString();

        // グラフ用データの更新 (CPU使用率はそのまま使用、100%を超えないようにする)
        setChartData(prevData => {
          const newData = [...prevData, {
            time: timeString,
            cpuTotal: data.cpu.total, // 元の値をそのまま使用 (0.0 〜 1.0)
            memoryUsage: data.cpu.memory,
            gpuUtilization: data.gpu.utilization,
            gpuMemoryUsage: (data.gpu.memory_used / data.gpu.memory_total) * 100 // パーセント表示に変換
          }];

          // データ点が多すぎる場合は古いものから削除 (60秒分のデータを保持)
          if (newData.length > 60) {
            return newData.slice(newData.length - 60);
          }
          return newData;
        });
      } catch (err) {
        console.error("リソース情報の取得に失敗しました:", err);
        setError(err instanceof Error ? err.message : "リソース情報の取得に失敗しました");
      }
    };

    // 初回データ取得
    fetchResourceData();

    // 1秒間隔でのデータ取得を設定
    intervalRef.current = setInterval(fetchResourceData, 1000);

    // クリーンアップ関数
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  // モニタリングの開始/停止を切り替える関数
  const toggleMonitoring = () => {
    if (isMonitoring) {
      // モニタリングを停止
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    } else {
      // モニタリングを再開
      const fetchResourceData = async () => {
        try {
          const response = await fetch(`${API_URL}/resource`);
          const errorMessage = response.headers.get("X-LEADABLE-ERROR-MESSAGE");
          if (errorMessage) {
            throw new Error(errorMessage);
          }

          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
          }

          const data: ResourceData = await response.json();
          setResourceData(data);

          const now = new Date();
          const timeString = now.toLocaleTimeString();

          setChartData(prevData => {
            const newData = [...prevData, {
              time: timeString,
              cpuTotal: data.cpu.total, // 元の値をそのまま使用
              memoryUsage: data.cpu.memory,
              gpuUtilization: data.gpu.utilization,
              gpuMemoryUsage: (data.gpu.memory_used / data.gpu.memory_total) * 100
            }];

            if (newData.length > 60) {
              return newData.slice(newData.length - 60);
            }
            return newData;
          });
        } catch (err) {
          console.error("リソース情報の取得に失敗しました:", err);
          setError(err instanceof Error ? err.message : "リソース情報の取得に失敗しました");
        }
      };

      // 即時に1回実行してからインターバル開始
      fetchResourceData();
      intervalRef.current = setInterval(fetchResourceData, 1000);
    }

    setIsMonitoring(!isMonitoring);
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl">
      <div className="flex justify-between items-center mb-6">
        <Link to="/" className="btn btn-sm btn-outline">
          <ArrowLeft size={18} className="mr-2" /> 一覧に戻る
        </Link>
        <button
          className={`btn btn-sm ${isMonitoring ? 'btn-error' : 'btn-success'}`}
          onClick={toggleMonitoring}
        >
          {isMonitoring ? 'モニタリング停止' : 'モニタリング開始'}
        </button>
      </div>

      <h2 className="text-2xl font-bold mb-4">システムリソースモニタ</h2>

      {error && (
        <div className="alert alert-error mb-4">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="stroke-current shrink-0 h-6 w-6"
            fill="none"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <span>{error}</span>
        </div>
      )}

      {resourceData && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <div className="card bg-base-100 shadow-xl">
            <div className="card-body">
              <h3 className="card-title">CPU 使用率</h3>
              <div className="text-3xl font-bold">{(resourceData.cpu.total * 100).toFixed(1)}%</div>
              <div className="mt-2">
                <div className="flex justify-between text-sm mb-1">
                  <span>使用率</span>
                  <span>{(resourceData.cpu.total * 100).toFixed(1)}%</span>
                </div>
                <progress
                  className="progress progress-primary"
                  value={resourceData.cpu.total * 100}
                  max="100"
                ></progress>
              </div>
            </div>
          </div>

          <div className="card bg-base-100 shadow-xl">
            <div className="card-body">
              <h3 className="card-title">メモリ使用率</h3>
              <div className="text-3xl font-bold">{resourceData.cpu.memory.toFixed(1)}%</div>
              <div className="mt-2">
                <div className="flex justify-between text-sm mb-1">
                  <span>使用率</span>
                  <span>{resourceData.cpu.memory.toFixed(1)}%</span>
                </div>
                <progress
                  className="progress progress-primary"
                  value={resourceData.cpu.memory}
                  max="100"
                ></progress>
              </div>
            </div>
          </div>

          <div className="card bg-base-100 shadow-xl">
            <div className="card-body">
              <h3 className="card-title">GPU 使用率</h3>
              <div className="text-3xl font-bold">{resourceData.gpu.utilization}%</div>
              <div className="mt-2">
                <div className="flex justify-between text-sm mb-1">
                  <span>使用率</span>
                  <span>{resourceData.gpu.utilization}%</span>
                </div>
                <progress
                  className="progress progress-primary"
                  value={resourceData.gpu.utilization}
                  max="100"
                ></progress>
              </div>
            </div>
          </div>

          <div className="card bg-base-100 shadow-xl">
            <div className="card-body">
              <h3 className="card-title">GPU メモリ使用率</h3>
              <div className="text-3xl font-bold">
                {resourceData.gpu.memory_used} / {resourceData.gpu.memory_total} MB
              </div>
              <div className="mt-2">
                <div className="flex justify-between text-sm mb-1">
                  <span>使用率</span>
                  <span>{((resourceData.gpu.memory_used / resourceData.gpu.memory_total) * 100).toFixed(1)}%</span>
                </div>
                <progress
                  className="progress progress-primary"
                  value={resourceData.gpu.memory_used}
                  max={resourceData.gpu.memory_total}
                ></progress>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="card bg-base-100 shadow-xl mt-6">
        <div className="card-body">
          <h3 className="card-title">リソース使用率の推移</h3>
          <div className="h-[400px] mt-4">
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={chartData}
                  margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="time"
                    tick={{ fontSize: 12 }}
                    interval="preserveStartEnd"
                  />
                  <YAxis domain={[0, 100]} />
                  <Tooltip />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="cpuTotal"
                    name="CPU 使用率"
                    stroke="#8884d8"
                    activeDot={{ r: 8 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="memoryUsage"
                    name="メモリ使用率"
                    stroke="#82ca9d"
                  />
                  <Line
                    type="monotone"
                    dataKey="gpuUtilization"
                    name="GPU 使用率"
                    stroke="#ff8042"
                  />
                  <Line
                    type="monotone"
                    dataKey="gpuMemoryUsage"
                    name="GPU メモリ使用率"
                    stroke="#ffc658"
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex justify-center items-center h-full">
                <span>データを取得中...</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
