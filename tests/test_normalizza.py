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


def test_lamiere_scritte_come_misure_non_sono_tubi():
    # reali: scritture dei DDT e dei certificati di un fascicolo (SP.0nn, L.DA TRENO, PLATES con spazi, coil)
    assert nz.profilo("SP.012X2450X6000") == "LAMIERA 12"
    assert nz.profilo("LAMIERE S355 SP.010X2000X6000 Placca: C2589A Colata: C2589") == "LAMIERA 10"
    assert (
        nz.profilo("ORD.INT.: 2587519 DEL 11/09/25 L.DA TRENO S355J2 EN 10025-2 Pz 8 6000x2500x15,00") == "LAMIERA 15"
    )
    assert nz.profilo("Hot Rolled Heavy Plates 15,00 X 2450,00 X 12000,00") == "LAMIERA 15"
    assert nz.profilo("HOT ROLLED PLATE 12x2500x6000") == "LAMIERA 12"
    assert nz.profilo("Hot Rolled Steel Plates overrolling and second e 10.00 2000 12000") == "LAMIERA 10"
    assert nz.profilo("Hot Rolled Mill Edge Coil 8,00x1660xC") == "LAMIERA 8"
    assert nz.profilo("Hot Rolled Mill Edge Strip 1500.0X8.00XCOIL") == "LAMIERA 8"
    assert nz.profilo("LAM. CALDO 5,00 x1500,00 x 6000,00") == "LAMIERA 5"
    assert nz.profilo("LAMIERA 60-10") == "PIATTO 60x10"  # scrittura di distinta: piatto 60x10
    assert nz.profilo("FERRO U 240X2500") == "UPN 240"
    # inventati: tre misure con una sola piccola = lamiera; due piccole e una lunghezza = tubo
    assert nz.profilo("8x1500x3000") == "LAMIERA 8"
    assert nz.profilo("PLATE 20 x 2000 x 6000") == "LAMIERA 20"
    assert nz.profilo("lamiera spess. 12 mm 1500x3000") == "LAMIERA 12"
    assert nz.profilo("4,35x1430xC") == "LAMIERA 4.35"
    assert nz.profilo("LAM 50-8") == "PIATTO 50x8"
    assert nz.profilo("LAM NERE 2000x1000x80/10") == "LAMIERA 8"
    # tubi: solo con la parola (TUBO, CRP, CHS, Ø) o nella forma diametro x spessore
    assert nz.profilo("TUBO ELETTROSALDATO SCORDONATO 219,1x12,5x12000") == "TUBO 219.1x12.5x12000"
    assert nz.profilo("N. 57 TUBO 76,1X5 L. 1320 mm") == "TUBO 76.1x5"
    assert nz.profilo("40x40x3") == "TUBO 40x40x3"
    assert nz.profilo("CHS 88,9x4") == "TUBO 88.9x4"
    assert nz.profilo("Ø 60,3x3,6") == "TUBO 60.3x3.6"
    assert nz.profilo("TUBO 12x2450x6000") == "TUBO 12x2450x6000"  # con la parola resta un tubo


def test_colata_per_il_confronto_e_colate_dichiarate_sulla_riga():
    # reali: prefisso di due lettere, suffisso corto, placca = colata + lettera
    assert nz.colata_normale("DU123329BJ0") == "123329" and nz.stessa_colata("DU123329BJ0", "123329")
    assert nz.stessa_colata("CE256775", "256775") and nz.stessa_colata("3151783B", "3151783")
    assert nz.stessa_colata("C2589A", "C2589") and not nz.stessa_colata("C2589", "C2590")
    assert not nz.stessa_colata("150890", "1508901") and not nz.stessa_colata("", "")
    # inventati
    assert nz.stessa_colata("PA 77 88 99", "778899") and not nz.stessa_colata("AB12", "12")
    reale = (
        "SP.015X2450X6000 Placca: 24E6061124(A) Colata: 143343 Placca: 24E6061124(B) Colata: 143343 "
        "Placca: 24E6061126(A) Colata: 442770"
    )
    assert nz.colate_dichiarate(reale) == [
        ("143343", ["24E6061124(A)", "24E6061124(B)"]),
        ("442770", ["24E6061126(A)"]),
    ]
    assert nz.colate_dichiarate("LAMIERE S355 SP.010X2000X6000 Placca: C2589A (01-01A) Colata: C2589") == [
        ("C2589", ["C2589A"])
    ]
    assert nz.colate_dichiarate("TUBO 88,9x4 CERT.COL. DU123329BJ0 L=6000") == [("DU123329BJ0", [])]
    assert nz.colate_dichiarate("HEA 200 S275JR heat no. 55123 plate id P7") == [("55123", [])]
    assert nz.colate_dichiarate("TRAVI HE/A 160 S355J2 L= 500") == []  # nessuna parola colata: niente
    assert nz.colate_dichiarate("contributo certificazione colata N. 12") == []  # meno di tre cifre
    assert nz.cita_ddt("51159", "G02 / 51159") and nz.cita_ddt("8027", "8027") and nz.cita_ddt("5678", "5678/1")
    assert not nz.cita_ddt("1159", "G02 / 51159") and not nz.cita_ddt("777", "1777")


def test_numero_contenuto_e_progressivo():
    assert nz.contiene_numero("DDT/DELIVNOTE BA/6577", "BA/6577") and not nz.contiene_numero("1066009422", "6577")
    assert nz.contiene_numero("Delivery note 2026/45678 del", "45678") and not nz.contiene_numero("x", "")
    assert nz.progressivo("G02 / 51159") == nz.progressivo("38747/ 51159") == "51159"
    assert nz.progressivo("8027") == "" and nz.progressivo("2026/45678") == "45678"


def test_tre_misure_con_spazi_senza_parola():
    assert nz.profilo("10.00 2000 12000") == "LAMIERA 10"  # campo dimensioni di un certificato
    assert nz.profilo("30.00 2000 10000") == "LAMIERA 30"
    assert nz.profilo("40 40 3") == "40 40 3"  # non è una lamiera: resta com'è


def test_numeri_con_o_per_zero_e_suffisso_con_trattino():
    """0.7.1 (Viollier): 'CO19604' dichiarato e 'C019604' letto sono lo stesso certificato; il timbro scrive il DDT
    '3209 - 1' per '3209/1'."""
    assert nz.stesso_numero("CO19604", "C019604") == "uguale"
    assert nz.stesso_numero("3209 - 1", "3209/1") == "uguale"
    assert nz.cita_ddt("3209 - 1", "3209") and nz.cita_ddt("3209 - 1", "3209/1")
    assert nz.stesso_numero("SP21-05850", "SP21-05850") == "uguale"  # il trattino con più cifre resta un prefisso
    assert nz.quasi_uguale("1002", "01062") and not nz.quasi_uguale("1002", "1062/1")
    assert not nz.quasi_uguale("1002", "2062") and not nz.quasi_uguale("12", "13")


def test_data_scritta_a_penna_e_angolare_con_misure_per_campo():
    assert nz.data_iso("18/5/22") == "2022-05-18"
    assert nz.data_iso("1/2/2026") == "2026-02-01"
    assert nz.data_iso("18/05/2022") == "2022-05-18"
    assert nz.profilo("ANGOLARE A LATI UGUALI LT=50.0 LT=50.0 SP=5.0 LU=L.C.") == "ANGOLARE 50 50 5"
    assert nz.profilo("ANGOLARE LT=100 LA=50 SP=6") == "ANGOLARE 100 50 6"
    assert nz.riconosciuta("PIATTO 70x10") and not nz.riconosciuta("LT=50.0 LT=50.0 SP=5.0 LU=L.C.")
