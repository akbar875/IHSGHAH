'use client';

import Link from 'next/link';
import { useCallback, useState } from 'react';
import { parseDailyStock } from '@/lib/daily-stock';
import { useDailyResource } from '@/lib/use-daily-resource';
import { BacktestChart, DailyHistoryChart } from './daily-charts';

const money = (v: string) => `Rp ${new Intl.NumberFormat('id-ID', { maximumFractionDigits: 2 }).format(Number(v))}`;
const stamp = (v: string) => `${new Date(v).toLocaleString('id-ID', { timeZone: 'Asia/Jakarta' })} WIB`;
export default function DailyStockDetail({ symbol }: { symbol: string }) {
  const [revision, setRevision] = useState(0);
  const [range, setRange] = useState(60);
  const parse = useCallback((value: unknown) => parseDailyStock(value, symbol), [symbol]);
  const resource = useDailyResource(`stocks/${encodeURIComponent(symbol)}`, parse, revision);
  const data = resource.data;
  return <main className="signal-page daily-stock-page">
    <Link href="/">← Daftar saham</Link>
    <header className="signal-heading"><div><p className="eyebrow">BEI · DETAIL SAHAM</p><h1>{symbol}</h1><p className="intro">{data ? `${money(data.close_idr)} · penutupan ${data.date}` : 'Chart, skenario harga, dan data antrean pasar.'}</p></div><button onClick={() => setRevision(v => v + 1)}>Muat ulang data</button></header>
    <div className="signal-meta"><span>Data harian · sinkronisasi 15 detik · feed real time belum terhubung</span><span>{resource.checked ? `Diperiksa ${stamp(resource.checked)}` : 'Menunggu data'}</span></div>
    <p role="status">{resource.loading ? 'Memuat detail saham…' : resource.error ?? 'Detail saham tersedia.'}</p>
    {data && <>
      {data.stale && <p className="signal-warning">Data tertinggal. Rencana terbaru tidak tersedia; riwayat dan backtest tetap diberi tanggal historis.</p>}
      {data.plan ? <section className="daily-plan" aria-label="Target dan risiko"><span className={`direction ${data.plan.direction}`}>{data.plan.direction === 'bullish' ? '↗ Bullish' : '↘ Bearish'}</span><dl className="stock-row-levels"><div><dt>Harga acuan</dt><dd>{money(data.plan.reference)}</dd></div><div><dt>{data.plan.direction === 'bullish' ? 'Take profit' : 'Target penurunan'}</dt><dd>{money(data.plan.take_profit)}</dd></div><div><dt>{data.plan.direction === 'bullish' ? 'Stop loss' : 'Batas invalidasi'}</dt><dd>{money(data.plan.stop_loss)}</dd></div><div><dt>Potensi ke target</dt><dd>{Number(data.plan.potential_pct).toFixed(2)}%</dd></div></dl></section> : <p className="muted">Saham ini tidak memenuhi filter bullish/bearish saat snapshot terakhir. Tidak ada target pengganti.</p>}
      <section className="panel detail-section" aria-labelledby="daily-history-title"><div className="daily-chart-heading"><div><h2 id="daily-history-title">Chart harga & volume</h2><p className="muted">Riwayat asli · tanggal dalam WIB · data per hari</p></div><div className="intervals" role="group" aria-label="Rentang riwayat">{[20, 60, 120, 253].map(n => <button key={n} aria-pressed={range === n} onClick={() => setRange(n)}>{n === 253 ? '1 tahun' : `${n} sesi`}</button>)}</div></div>
        <DailyHistoryChart data={data} range={range} />
        <p className="chart-attribution">TradingView Lightweight Charts™ · <a href="https://www.tradingview.com/">TradingView</a> · <a href="https://www.apache.org/licenses/LICENSE-2.0">Apache-2.0</a></p>
      </section>
      <section className="panel detail-section" aria-labelledby="daily-backtest-title"><h2 id="daily-backtest-title">Backtest transaksi historis</h2><p className="muted">Target 1.000 transaksi unik per saham · strategi beli saja · pengujian eksploratif</p>
        {data.backtest ? <>
          <p className="backtest-count"><strong>{data.backtest.completed_trades.toLocaleString('id-ID')}</strong> / 1.000 transaksi selesai</p>
          {!data.backtest.target_reached && <p className="signal-warning">Belum mencapai 1.000 transaksi. Data hanya menghasilkan {data.backtest.completed_trades} transaksi yang selesai; transaksi tidak digandakan atau dianggap sampel independen tambahan.</p>}
          {data.backtest.status === 'data_gap' && <p className="signal-warning">Ada data tidak layak atau celah saat posisi masih terbuka. Pengujian dihentikan; metrik ringkasan tidak diterbitkan.</p>}
          {data.backtest.unclosed_position && <p className="muted">Ada posisi hipotetis yang belum selesai di akhir data. Posisi ini tidak dihitung sebagai transaksi selesai.</p>}
          <dl className="stock-row-levels backtest-metrics"><div><dt>Transaksi positif</dt><dd>{data.backtest.win_count}</dd></div><div><dt>Transaksi negatif</dt><dd>{data.backtest.loss_count}</dd></div><div><dt>Hasil kumulatif bersih</dt><dd>{data.backtest.total_return_pct === null ? 'Belum tersedia' : `${data.backtest.total_return_pct.toFixed(2)}%`}</dd></div><div><dt>Drawdown maksimum</dt><dd>{data.backtest.max_drawdown_pct === null ? 'Belum tersedia' : `${data.backtest.max_drawdown_pct.toFixed(2)}%`}</dd></div></dl>
          {!!data.backtest.trades.length && <><BacktestChart backtest={data.backtest} /><div className="backtest-trades"><table><caption>20 transaksi selesai terakhir · tanggal EOD WIB</caption><thead><tr><th>Entry</th><th>Exit</th><th>Hasil bersih</th><th>Alasan keluar</th></tr></thead><tbody>{data.backtest.trades.slice(-20).reverse().map(t => <tr key={`${t.entry_date}:${t.exit_date}`}><td>{t.entry_date}</td><td>{t.exit_date}</td><td className={t.net_return_pct >= 0 ? 'trade-profit' : 'trade-loss'}>{t.net_return_pct.toFixed(2)}%</td><td>{t.exit_reason === 'stop_close' ? 'Stop penutupan' : t.exit_reason === 'target_close' ? 'Target penutupan' : '15 sesi'}</td></tr>)}</tbody></table></div></>}
          <details className="simulation-method"><summary>Aturan, biaya & batas pengujian</summary><p>Filter MA20/50/200, RSI14, momentum dan likuiditas dibaca pada penutupan hari sinyal. Entry pada penutupan sesi berikutnya, satu posisi per saham. Keluar pada penutupan pertama yang melewati stop/target atau setelah 15 sesi. Return memakai adjusted return penyedia. Stop tidak diasumsikan tereksekusi tepat di levelnya.</p><p>Asumsi biaya beli {(data.backtest.buy_fee * 100).toFixed(2)}%, jual {(data.backtest.sell_fee * 100).toFixed(2)}%, slippage {(data.backtest.slippage_each_side * 100).toFixed(2)}% per sisi. Ini simulasi eksposur pecahan, belum memodelkan lot, antrean, fill intraday, suspensi atau aturan bursa saat itu.</p><p>Periode {data.backtest.start_date}–{data.backtest.end_date}. Universe historis dan waktu ketersediaan fitur penyedia belum diaudit; ada risiko survivorship dan hindsight. Belum holdout, bukan hasil transaksi nyata, dan hasil masa lalu tidak menjadi probabilitas harga mendatang. Untuk saham bearish, hasil ini tetap menguji strategi beli historis, bukan short selling.</p></details>
        </> : <p>Hasil backtest belum tersedia pada snapshot ini. Impor ulang data harian untuk menghitung transaksi historis; angka 1.000 tidak dianggap tercapai sebelum ada 1.000 transaksi selesai.</p>}
      </section>
      <div className="daily-depth-grid"><section className="panel detail-section" aria-labelledby="daily-book-title"><h2 id="daily-book-title">Order book</h2><span className="unavailable-tag">Feed belum terhubung</span><p>Bid, ask, harga, volume dan waktu snapshot akan tampil setelah feed order book tersedia.</p><p className="muted">Data penutupan harian tidak memuat antrean beli/jual. Tidak ada angka order book yang dibuat dari estimasi.</p></section>
        <section className="panel detail-section" aria-labelledby="daily-queue-title"><h2 id="daily-queue-title">Antrean order</h2><span className="unavailable-tag">Belum tersedia</span><p>Antrean per harga memerlukan data kedalaman pasar. Jumlah order dan posisi antrean individual memerlukan dukungan khusus penyedia.</p><p className="muted">Volume bid/ask agregat tidak membuktikan urutan order milikmu dalam antrean.</p></section></div>
      <footer className="signal-footer"><p><a href={data.source}>Aethereal</a> · <a href={data.license_url}>CC BY 4.0</a> · {data.attribution}</p><p>Snapshot diimpor {stamp(data.available_at)}. Memeriksa server setiap 15 detik tidak mengubah data harian menjadi real time. Target dan stop merupakan skenario teknikal; untuk bearish, target turun dan invalidasi bukan TP/SL posisi beli.</p></footer>
    </>}
  </main>;
}
