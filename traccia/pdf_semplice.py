"""PDF di una pagina con righe di testo (Helvetica), scritto a mano: serve al cantiere di prova, nessuna libreria."""

A5 = (420, 595)
A4 = (595, 842)


def _escape(testo: str) -> str:
    return (
        testo.encode("latin-1", "replace")
        .decode("latin-1")
        .replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


def pdf_con_testo(righe: list[str], formato: tuple[int, int] = A4, corpo: int = 10) -> bytes:
    larghezza, altezza = formato
    flusso = f"BT /F1 {corpo} Tf 40 {altezza - 50} Td {corpo + 3} TL\n"
    flusso += "".join(f"({_escape(r)}) Tj T*\n" for r in righe) + "ET"
    oggetti = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {larghezza} {altezza}] "
        "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(flusso.encode('latin-1'))} >>\nstream\n{flusso}\nendstream",
    ]
    corpo_pdf, posizioni = b"%PDF-1.4\n", []
    for i, o in enumerate(oggetti, 1):
        posizioni.append(len(corpo_pdf))
        corpo_pdf += f"{i} 0 obj\n{o}\nendobj\n".encode("latin-1")
    xref = len(corpo_pdf)
    corpo_pdf += f"xref\n0 {len(oggetti) + 1}\n0000000000 65535 f \n".encode()
    corpo_pdf += "".join(f"{p:010d} 00000 n \n" for p in posizioni).encode()
    corpo_pdf += f"trailer\n<< /Size {len(oggetti) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return corpo_pdf
