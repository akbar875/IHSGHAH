import { publicConfig } from '@/lib/config';
import Link from 'next/link';

export default function Home() {
  return (
    <>
      <a className="skip-link" href="#utama">Lewati ke konten</a>
      <header className="header">
        <Link className="brand" href="/" aria-label="Saham Signal, beranda">
          <span className="brand-icon" aria-hidden="true">S</span>
          <span>Saham<span className="brand-light"> Signal</span></span>
        </Link>
        <span className="mode">Research / Simulasi</span>
      </header>
      <main id="utama" className="workspace">
        <div className="eyebrow">RUANG KERJA RESEARCH</div>
        <h1>Mulai dari fondasi.</h1>
        <p className="intro">Ruang analisis saham intraday untuk keputusan yang terukur. Saat ini aplikasi berada dalam tahap persiapan.</p>
        <section className="notice" aria-labelledby="simulation-title">
          <span className="notice-icon" aria-hidden="true">i</span>
          <div><h2 id="simulation-title">Lingkungan simulasi</h2>
            <p>Belum ada feed pasar, harga, atau sinyal. Data dan fitur research tidak boleh digunakan untuk transaksi nyata.</p>
          </div>
        </section>
        <section className="panel" aria-labelledby="workspace-title">
          <div className="panel-heading"><h2 id="workspace-title">Ringkasan ruang kerja</h2><span className="tag">Persiapan</span></div>
          <dl className="status-grid">
            <div><dt>Mode aplikasi</dt><dd>{publicConfig.mode}</dd></div>
            <div><dt>Sumber data</dt><dd>Simulasi · belum tersedia</dd></div>
            <div><dt>Feed pasar</dt><dd>Belum terhubung</dd></div>
            <div><dt>Zona waktu tampilan</dt><dd>{publicConfig.displayTimezone}</dd></div>
          </dl>
          <div className="empty-state">
            <span className="empty-icon" aria-hidden="true">—</span>
            <h3>Belum ada data untuk ditampilkan</h3>
            <p>Kandidat saham, watchlist, dan posisi akan tersedia pada tahap pengembangan berikutnya.</p>
          </div>
        </section>
        <p className="footnote">READY tidak membuka posisi. Keputusan dan pencatatan transaksi tetap dilakukan secara manual.</p>
      </main>
      <footer className="footer"><span>Saham Signal</span><span>Research / Simulasi · Asia/Jakarta</span></footer>
    </>
  );
}
