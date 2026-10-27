"""PDF di una pagina A4 con righe di testo (Helvetica), scritto a mano: nessuna libreria, solo per i test."""


def _escape(testo: str) -> str:
    return (
        testo.encode("latin-1", "replace")
        .decode("latin-1")
        .replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


def pdf_con_testo(righe: list[str]) -> bytes:
    flusso = "BT /F1 10 Tf 50 790 Td 12 TL\n" + "".join(f"({_escape(r)}) Tj T*\n" for r in righe) + "ET"
    oggetti = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(flusso.encode('latin-1'))} >>\nstream\n{flusso}\nendstream",
    ]
    corpo, posizioni = b"%PDF-1.4\n", []
    for i, o in enumerate(oggetti, 1):
        posizioni.append(len(corpo))
        corpo += f"{i} 0 obj\n{o}\nendobj\n".encode("latin-1")
    xref = len(corpo)
    corpo += f"xref\n0 {len(oggetti) + 1}\n0000000000 65535 f \n".encode()
    corpo += "".join(f"{p:010d} 00000 n \n" for p in posizioni).encode()
    corpo += f"trailer\n<< /Size {len(oggetti) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return corpo
