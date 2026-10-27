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


def test_numeri_di_documento():
    assert nz.stesso_numero("1234", "1234 2021") == "uguale"  # numero + anno stampati separati
    assert nz.stesso_numero("731", "00731") == "uguale"
    assert nz.stesso_numero("45678", "2026/45678") == "uguale"
    assert nz.stesso_numero("5678", "5678/1") == "serie"
    assert nz.stesso_numero("777", "99-777") == "prefisso"
    assert nz.stesso_numero("4455", "16624455") is None  # numero corto senza separatore: non basta
    assert nz.stesso_numero("12345678", "99912345678") == "prefisso"
    assert nz.stesso_numero("1777", "7777") is None
