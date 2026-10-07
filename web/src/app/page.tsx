import {
  ArrowRight,
  Brain,
  Copy,
  Eraser,
  Eye,
  FileText,
  ShieldCheck,
  Sparkles,
  Undo2,
  Zap,
} from "lucide-react";
import Link from "next/link";
import { Brand } from "@/components/sidebar";

const FEATURES = [
  { icon: Brain, title: "Versteht Inhalte", text: "Rechnungen, Verträge, Steuerunterlagen – per KI & OCR erkannt und nach Finanzen/Rechnungen/2026 einsortiert." },
  { icon: FileText, title: "Sprechende Dateinamen", text: "Aus SCAN_2026_09_12.pdf wird 2026-09-12_Telekom_Rechnung_89Euro.pdf." },
  { icon: Copy, title: "Duplikat-Erkennung", text: "Exakt per SHA-256 und inhaltlich ähnlich per pHash (Bilder) und SimHash (PDFs)." },
  { icon: Zap, title: "Medien-Optimierung", text: "Verlustfreie oder verlustbehaftete Komprimierung für PNG, JPG, WEBP und Videos." },
  { icon: Eraser, title: "Smart Cleanup", text: "Alte Installer, abgebrochene Downloads, Temp-Dateien und leere Ordner – gelöscht erst nach Freigabe." },
  { icon: Eye, title: "Dry-Run-Vorschau", text: "Sieh genau, was passieren WÜRDE, bevor irgendetwas verändert wird." },
  { icon: Undo2, title: "Undo mit einem Klick", text: "Jede Aktion steht im Manifest. Verschieben, Umbenennen, Löschen – alles umkehrbar." },
  { icon: ShieldCheck, title: "Safe-List", text: "Ordner, Dateitypen und Tags, die niemals angefasst werden." },
];

export default function Home() {
  return (
    <div className="min-h-screen">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <Brand />
        <div className="flex gap-2">
          <Link href="/login" className="btn">
            Anmelden
          </Link>
          <Link href="/login?mode=signup" className="btn btn-primary hidden sm:inline-flex">
            Kostenlos starten
          </Link>
        </div>
      </header>

      <section className="mx-auto max-w-6xl px-6 pb-16 pt-12 text-center">
        <span className="badge mb-6 bg-indigo-500/10 px-3 py-1 text-indigo-700 dark:text-indigo-300">
          <Sparkles className="size-3.5" /> Lokales LLM, OpenAI oder Claude
        </span>
        <h1 className="mx-auto max-w-3xl text-4xl font-semibold tracking-tight sm:text-6xl">
          Dein Download-Ordner,{" "}
          <span className="bg-gradient-to-r from-indigo-500 to-violet-500 bg-clip-text text-transparent">endlich aufgeräumt.</span>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-muted">
          Ein lokaler Agent liest, benennt und sortiert deine Dateien. Du behältst die Kontrolle: Jede Änderung erscheint zuerst als
          Vorschau im Dashboard und lässt sich jederzeit rückgängig machen.
        </p>
        <div className="mt-8 flex justify-center gap-3">
          <Link href="/login?mode=signup" className="btn btn-primary px-5 py-3">
            Jetzt einrichten <ArrowRight className="size-4" />
          </Link>
          <a href="https://github.com/vexsternbrink-hue/DateiSortieren" className="btn px-5 py-3">
            Auf GitHub ansehen
          </a>
        </div>

        <div className="card mx-auto mt-14 max-w-3xl break-all p-5 text-left font-mono text-sm">
          <div className="text-muted">~/Downloads/SCAN_2026_09_12.pdf</div>
          <div className="my-2 flex items-center gap-2 text-indigo-600 dark:text-indigo-300">
            <ArrowRight className="size-4" /> ~/Dokumente/Sortiert/Finanzen/Rechnungen/2026/
          </div>
          <div className="font-semibold">2026-09-12_Telekom_Rechnung_89Euro.pdf</div>
          <div className="mt-3 flex flex-wrap gap-2 font-sans">
            <span className="badge bg-amber-500/15 text-amber-700 dark:text-amber-300">Vorschlag</span>
            <span className="badge bg-surface-muted text-muted">#rechnung</span>
            <span className="badge bg-surface-muted text-muted">#telekom</span>
            <span className="badge bg-emerald-500/15 text-emerald-700 dark:text-emerald-300">KI-Sicherheit 97%</span>
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-4 px-6 pb-24 sm:grid-cols-2 lg:grid-cols-4">
        {FEATURES.map(({ icon: Icon, title, text }) => (
          <div key={title} className="card p-5">
            <Icon className="mb-3 size-5 text-indigo-500" />
            <h3 className="font-medium">{title}</h3>
            <p className="mt-1 text-sm text-muted">{text}</p>
          </div>
        ))}
      </section>

      <footer className="border-t border-border py-8 text-center text-sm text-muted">
        Deine Dateien verlassen nie deinen Rechner – das Dashboard sieht nur Pfade und Vorschläge.
      </footer>
    </div>
  );
}
