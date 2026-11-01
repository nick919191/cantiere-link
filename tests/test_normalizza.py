from traccia import normalizza as nz


def test_scritture_di_distinta_e_per_campo():
    assert nz.profilo("PL10*80") == "PIATTO 80x10"
    assert nz.profilo("L60*6") == "ANGOLARE 60 60 6"
    assert nz.profilo("PIATTO LT=100,0 SP=10,0 LU=L.C.") == "PIATTO 100x10"
    assert nz.profilo("LARGHI PIATTI LA=160 SP=10") == "PIATTO 160x10"
    assert nz.profilo("FLAT 160X10") == "PIATTO 160x10"
    assert nz.profilo("TUBI SALD. RETTANGOLARI LT=30 AL=10 SP=1,5") == "TUBO 30x10x1.5"
    assert nz.profilo("LAM.TRENO S355J2 SP=8 LA=2450") == "LAMIERA 8"
    assert nz.profilo("LAMIERA 8x2000x6000") == "LAMIERA 8"
    assert nz.profilo("ANGLE 40X40X4") == "ANGOLARE 40 40 4"
    assert nz.profilo("HEB180") == "HEB 180"


def test_gradi_con_alternative():
    assert nz.gradi("S275JR/J0") == {"S275JR", "S275J0"}
    assert nz.gradi("S 355 J2") == {"S355J2"}


def test_data_iso_anche_dentro_il_testo_della_colonna():
    assert nz.data_iso("05/06/2026") == "2026-06-05"
    assert nz.data_iso("DDT n. 123 del 01/02/2026") == "2026-02-01"  # M8: la colonna DDT ordinata per data
    assert nz.data_iso("senza data") == "senza data" and nz.data_iso(None) == ""


def test_numeri_di_documento():
    assert nz.stesso_numero("1234", "1234 2021") == "uguale"  # numero + anno stampati separati
    assert nz.stesso_numero("731", "00731") == "uguale"
    assert nz.stesso_numero("45678", "2026/45678") == "uguale"
    assert nz.stesso_numero("5678", "5678/1") == "serie"
    assert nz.stesso_numero("777", "99-777") == "prefisso"
    assert nz.stesso_numero("4455", "16624455") is None  # numero corto senza separatore: non basta
    assert nz.stesso_numero("12345678", "99912345678") == "prefisso"
    assert nz.stesso_numero("1777", "7777") is None


def test_nucleo_della_ragione_sociale_senza_indirizzo_ne_forma_giuridica():
    # reali (Codogno): sette forme della stessa azienda, con indirizzo, sigla per esteso, suffisso incollato
    forme = [
        "S.A.C.I.F. SRL VIA NULLO N.5 20129 MILANO",
        "SACIF SRL",
        "S.A.C.I.F. S.R.L.\nVIA NULLO, 5\n20129 MILANO",
        "S.A.C.I.F. SRL SOCIETA' AMBROSIANA COSTRUZIONI IN FERRO VIA NULLO, 5 20129 MILANO",
        "Società Ambrosiana Costruzioni In Ferro Srl",
        "SACIF S.r.l.",
        "S.A.C.I.F. SRL SOCIETA' AMBROSIANA COSTR",
    ]
    assert all(nz.stessa_azienda(forme[0], f) for f in forme)
    assert nz.aziende("S.A.C.I.F. SRL VIA NULLO N.5 20129 MILANO") == {"sacif"}
    assert nz.aziende("SETAL S.P.A.") == nz.aziende("SETALS.P.A.") == {"setal"}
    assert nz.stessa_azienda("FVS S.p.A.", "FERRAMENTA VILLAFRANCA SIDERURGICA S.p.A.")  # sigla dalle iniziali
    assert nz.stessa_azienda("Gabrielli S.p.A. - Società Unipersonale", "GABRIELLI SPA UNIPERSONALE / Divisione Coils")
    # inventati: indirizzo, sigla, suffisso incollato, reparto
    assert nz.stessa_azienda("Tubificio Nord Srl Via Roma 1 10100 Torino", "TUBIFICIO NORD")
    assert nz.stessa_azienda("Acciaierie Rossi e Bianchi S.p.A.", "ARB SPA")
    assert nz.aziende("LAMIERENORDSRL") == {"lamierenord"}
    assert nz.stessa_azienda("Ferriera Sud S.p.A. Stabilimento di Taranto", "FERRIERA SUD")
    # non la stessa azienda: prima parola comune, sigle diverse, nomi diversi
    assert not nz.stessa_azienda("Costruzioni 001 SRL", "Costruzioni 002 SRL")
    assert not nz.stessa_azienda("Acciaierie Rossi e Bianchi S.p.A.", "Acciaierie Verdi")
    assert not nz.stessa_azienda("SACIF SRL", "FVS S.p.A.")
    assert not nz.stessa_azienda("Marcegaglia Plates", "Marcegaglia Palini e Bertoli S.P.A.")
    # alias del fascicolo (stessa partita IVA)
    gruppi = [["ALFA SRL", "Officine Beta S.p.A."]]
    assert nz.stessa_azienda("ALFA S.R.L.", "OFFICINE BETA", gruppi)
    assert not nz.stessa_azienda("ALFA S.R.L.", "GAMMA", gruppi)


def test_partita_iva():
    assert nz.piva("Partita IVA 00716810155") == "00716810155"
    assert nz.piva("IT 00362740284") == "00362740284"
    assert nz.piva("123") == "" and nz.piva(None) == ""
