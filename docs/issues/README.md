# Backlog issue

`backlog.json` adalah manifest berurutan; setiap file `SS-xxx-*.md` adalah body issue yang siap diterbitkan. [Indeks backlog](../BACKLOG.md) memetakan urutan, prioritas, dependency, dan gerbang. ID SS stabil walaupun nomor GitHub berbeda.

## Menerbitkan

```sh
node scripts/check-scaffold.mjs
node scripts/publish-issues.mjs
node scripts/publish-issues.mjs --publish
```

Perintah tanpa `--publish` adalah dry run offline. Penerbitan menggunakan `GH_TOKEN`/`GITHUB_TOKEN` dari environment, atau sesi Git Credential Manager untuk `github.com`. Akun harus memiliki akses membuat issue pada `akbar875/IHSGHAH`; token fine-grained perlu akses repository dan Issues read/write. Jangan simpan token dalam repo atau argumen perintah.

Script memeriksa semua issue open/closed, melewati ID yang sudah diterbitkan, lalu membuat issue berurutan dengan tautan dependency sebenarnya. Script berhenti pada kegagalan; jalankan ulang setelah akses diperbaiki. Issue lama tidak ditimpa, dan issue dengan ID duplikat harus diselesaikan manual. Jalankan satu publisher pada satu waktu agar tidak terjadi balapan.

## Mengambil pekerjaan

Pilih issue tanpa dependency tersisa. Buat branch dari `main` menggunakan nomor GitHub sebenarnya: `feat/123-slug`. Usulan branch dalam body issue menggunakan placeholder `<issue-number>`. Setelah selesai, buat PR dengan `Closes #123` dan bukti validasi.

P0 = fondasi atau blokir validasi/rilis. P1 = kebutuhan inti MVP. P2 = tahap akhir pilot. Prioritas tidak menggantikan urutan dependency atau gerbang PRD.
