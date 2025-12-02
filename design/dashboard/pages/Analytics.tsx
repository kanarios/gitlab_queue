import React from 'react';
import { QueueStats } from '../types';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, Legend, PieChart, Pie, Cell } from 'recharts';
import { ArrowUpRight, ArrowDownRight, Clock, GitMerge } from 'lucide-react';
import { generateAnalyticsData } from '../mockData';

interface AnalyticsProps {
  stats: QueueStats;
}

const data = generateAnalyticsData();
const pieData = [
    { name: 'Success', value: 400 },
    { name: 'Failed', value: 45 },
    { name: 'Conflict', value: 25 },
];
const COLORS = ['#22c55e', '#ef4444', '#eab308'];

const Analytics: React.FC<AnalyticsProps> = ({ stats }) => {
  return (
    <div className="space-y-6 md:space-y-8">
      <h2 className="text-2xl md:text-3xl font-bold text-slate-900 dark:text-white mb-6">Queue Analytics</h2>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-slate-800/50 p-6 rounded-2xl border border-slate-200 dark:border-slate-700/50 backdrop-blur-sm shadow-sm">
            <div className="flex justify-between items-start">
                <div className="p-2 bg-blue-50 dark:bg-blue-900/30 rounded-lg">
                    <GitMerge className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                </div>
                <span className="flex items-center text-green-600 dark:text-green-400 text-xs font-bold bg-green-50 dark:bg-green-900/20 px-2 py-1 rounded-full border border-green-100 dark:border-green-900/30">
                    +12% <ArrowUpRight className="w-3 h-3 ml-1" />
                </span>
            </div>
            <h4 className="text-slate-500 dark:text-slate-400 text-sm mt-4 font-medium">Total Processed</h4>
            <p className="text-3xl font-bold text-slate-900 dark:text-white mt-1">{stats.totalProcessed}</p>
        </div>

        <div className="bg-white dark:bg-slate-800/50 p-6 rounded-2xl border border-slate-200 dark:border-slate-700/50 backdrop-blur-sm shadow-sm">
            <div className="flex justify-between items-start">
                <div className="p-2 bg-orange-50 dark:bg-orange-900/30 rounded-lg">
                    <Clock className="w-6 h-6 text-orange-600 dark:text-orange-400" />
                </div>
                <span className="flex items-center text-red-600 dark:text-red-400 text-xs font-bold bg-red-50 dark:bg-red-900/20 px-2 py-1 rounded-full border border-red-100 dark:border-red-900/30">
                    +2m <ArrowUpRight className="w-3 h-3 ml-1" />
                </span>
            </div>
            <h4 className="text-slate-500 dark:text-slate-400 text-sm mt-4 font-medium">Avg. Wait Time</h4>
            <p className="text-3xl font-bold text-slate-900 dark:text-white mt-1">{stats.avgWaitTimeMinutes} min</p>
        </div>

        <div className="bg-white dark:bg-slate-800/50 p-6 rounded-2xl border border-slate-200 dark:border-slate-700/50 backdrop-blur-sm shadow-sm">
             <div className="flex justify-between items-start">
                <div className="p-2 bg-green-50 dark:bg-green-900/30 rounded-lg">
                    <ArrowUpRight className="w-6 h-6 text-green-600 dark:text-green-400" />
                </div>
                <span className="flex items-center text-green-600 dark:text-green-400 text-xs font-bold bg-green-50 dark:bg-green-900/20 px-2 py-1 rounded-full border border-green-100 dark:border-green-900/30">
                    +2.4% <ArrowUpRight className="w-3 h-3 ml-1" />
                </span>
            </div>
            <h4 className="text-slate-500 dark:text-slate-400 text-sm mt-4 font-medium">Success Rate</h4>
            <p className="text-3xl font-bold text-slate-900 dark:text-white mt-1">{stats.successRate}%</p>
        </div>
        
         <div className="bg-white dark:bg-slate-800/50 p-6 rounded-2xl border border-slate-200 dark:border-slate-700/50 backdrop-blur-sm shadow-sm">
             <div className="flex justify-between items-start">
                <div className="p-2 bg-purple-50 dark:bg-purple-900/30 rounded-lg">
                    <ArrowDownRight className="w-6 h-6 text-purple-600 dark:text-purple-400" />
                </div>
            </div>
            <h4 className="text-slate-500 dark:text-slate-400 text-sm mt-4 font-medium">Daily Throughput</h4>
            <p className="text-3xl font-bold text-slate-900 dark:text-white mt-1">42 MRs</p>
        </div>
      </div>

      {/* Main Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="bg-white dark:bg-slate-800/50 p-6 rounded-2xl border border-slate-200 dark:border-slate-700/50 backdrop-blur-sm shadow-sm">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-6">Queue Depth (24h)</h3>
            <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={data}>
                        <defs>
                            <linearGradient id="colorQueue" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#8a2be2" stopOpacity={0.3}/>
                                <stop offset="95%" stopColor="#8a2be2" stopOpacity={0}/>
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" strokeOpacity={0.4} vertical={false} />
                        <XAxis dataKey="hour" stroke="#94a3b8" tick={{fontSize: 12}} />
                        <YAxis stroke="#94a3b8" tick={{fontSize: 12}} />
                        <Tooltip 
                            contentStyle={{ backgroundColor: 'rgba(30, 41, 59, 0.9)', borderColor: '#334155', color: '#f8fafc', borderRadius: '8px' }}
                            itemStyle={{ color: '#e2e8f0' }}
                        />
                        <Area type="monotone" dataKey="queueDepth" stroke="#8a2be2" strokeWidth={3} fillOpacity={1} fill="url(#colorQueue)" />
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        </div>

        <div className="bg-white dark:bg-slate-800/50 p-6 rounded-2xl border border-slate-200 dark:border-slate-700/50 backdrop-blur-sm shadow-sm">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-6">Merge Duration vs Success</h3>
            <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" strokeOpacity={0.4} vertical={false} />
                        <XAxis dataKey="hour" stroke="#94a3b8" tick={{fontSize: 12}} />
                        <YAxis stroke="#94a3b8" tick={{fontSize: 12}} />
                        <Tooltip 
                             contentStyle={{ backgroundColor: 'rgba(30, 41, 59, 0.9)', borderColor: '#334155', color: '#f8fafc', borderRadius: '8px' }}
                             cursor={{fill: '#334155', opacity: 0.2}}
                        />
                        <Legend />
                        <Bar dataKey="avgMergeTime" name="Avg Time (m)" fill="#fc6d26" radius={[4, 4, 0, 0]} />
                    </BarChart>
                </ResponsiveContainer>
            </div>
        </div>
      </div>

       <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
             <div className="bg-white dark:bg-slate-800/50 p-6 rounded-2xl border border-slate-200 dark:border-slate-700/50 backdrop-blur-sm shadow-sm lg:col-span-1">
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-6">Outcome Distribution</h3>
                <div className="h-64 w-full flex justify-center">
                    <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                            <Pie
                                data={pieData}
                                innerRadius={60}
                                outerRadius={80}
                                paddingAngle={5}
                                dataKey="value"
                            >
                                {pieData.map((entry, index) => (
                                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                ))}
                            </Pie>
                            <Tooltip contentStyle={{ backgroundColor: 'rgba(30, 41, 59, 0.9)', borderColor: '#334155', color: '#f8fafc', borderRadius: '8px' }} />
                            <Legend />
                        </PieChart>
                    </ResponsiveContainer>
                </div>
            </div>
            <div className="bg-white dark:bg-slate-800/50 p-6 rounded-2xl border border-slate-200 dark:border-slate-700/50 backdrop-blur-sm shadow-sm lg:col-span-2">
                 <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">Failure Reasons</h3>
                 <div className="space-y-4">
                     {[
                         { reason: 'Merge Conflict', count: 25, percent: 55 },
                         { reason: 'Pipeline Timeout', count: 12, percent: 26 },
                         { reason: 'Test Failure: Unit', count: 5, percent: 11 },
                         { reason: 'Test Failure: E2E', count: 3, percent: 8 },
                     ].map((item, idx) => (
                         <div key={idx} className="flex items-center text-sm">
                             <div className="w-48 text-slate-600 dark:text-slate-400">{item.reason}</div>
                             <div className="flex-1 h-2 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden mx-4">
                                 <div className="h-full bg-red-500 rounded-full" style={{width: `${item.percent}%`}}></div>
                             </div>
                             <div className="w-12 text-right font-mono text-slate-700 dark:text-slate-300">{item.count}</div>
                         </div>
                     ))}
                 </div>
            </div>
       </div>
    </div>
  );
};

export default Analytics;