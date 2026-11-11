# -*- coding: utf-8 -*-
"""VOX-Forense - CLI.
  python main.py analizar AUDIO.mp3 [--modo directo|crew]   analiza un audio (crew requiere clave de API del LLM)
  python main.py lote --carpeta DIR | --csv rasgos.csv [--salida out.csv]   analisis en lote sin LLM
  python main.py auditar rasgos.csv [--todo]                valores de Shapley y ablacion de agentes
  python main.py calibrar rasgos.csv [--todo]               recalibra umbrales y regenera la ontologia .owx"""
import argparse, json, sys


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("analizar"); a.add_argument("audio"); a.add_argument("--modo", choices=["directo", "crew"], default="directo")
    a.add_argument("--modelo", default=None, help="modelo LLM (por defecto VOX_LLM)")
    l = sp.add_parser("lote"); l.add_argument("--carpeta"); l.add_argument("--csv"); l.add_argument("--salida", default="salidas/resultados_lote.csv")
    u = sp.add_parser("auditar"); u.add_argument("csv"); u.add_argument("--todo", action="store_true", help="usar todos los audios y no solo los de prueba")
    c = sp.add_parser("calibrar"); c.add_argument("csv"); c.add_argument("--todo", action="store_true")
    args = ap.parse_args()

    if args.cmd == "analizar":
        if args.modo == "crew":
            from vox.crew import analizar_con_crew
            from vox.agentes import crear_llm
            r = analizar_con_crew(args.audio, crear_llm(args.modelo))
            print("\n=== RESULTADO (herramienta decidir_veredicto) ===\nVeredicto:", r["veredicto"]); print(r["explicacion"] or "")
            print("\n=== INFORME DEL LLM ===\n" + r["informe_llm"])
        else:
            from vox.pipeline import analizar_directo
            r = analizar_directo(args.audio); print("Licitacion:", r.get("licitacion"), "| Veredicto:", r["veredicto"]); print(r.get("explicacion", r.get("error")))
    elif args.cmd == "lote":
        if not (args.carpeta or args.csv): sys.exit("Indica --carpeta o --csv")
        import os; os.makedirs(os.path.dirname(args.salida) or ".", exist_ok=True)
        from vox.pipeline import analizar_lote
        df = analizar_lote(args.carpeta, args.csv, args.salida)
        print(df.veredicto.value_counts().to_string())
        if "etiqueta_real" in df:
            dec = df[df.veredicto.isin(["SINTETICO", "AUTENTICO"])]
            ok = ((dec.veredicto == "SINTETICO") == (dec.etiqueta_real == "fake")).sum()
            print(f"Resueltos: {len(dec)}/{len(df)} | aciertos entre resueltos: {ok}/{len(dec)} | escalados: {len(df)-len(dec)}")
        print("Guardado en", args.salida)
    elif args.cmd == "auditar":
        from vox.auditoria import auditar
        r = auditar(args.csv, solo_prueba=not args.todo)
        print(f"Audios: {r['n']} | exactitud global {r['exactitud_global']:.3f} | escalados {r['escalados']:.3f} | errores {r['errores']:.3f} | exactitud en resueltos {r['exactitud_resueltos']:.3f}")
        print(r["tabla"].round(3).to_string(index=False)); print(f"Suma de phi = {r['suma_phi']:.3f}  v(N) = {r['v_N']:.3f}")
    elif args.cmd == "calibrar":
        from vox.calibracion import calibrar
        cfg = calibrar(args.csv, todo=args.todo); print(json.dumps(cfg["meta"], ensure_ascii=False, indent=1))
        for ag in cfg["reglas"]:
            for r in cfg["reglas"][ag]: print(ag, r["feature"], "AUC", r["auc"], "t_indicio", round(r["t_ind"], 6), "t_natural", round(r["t_nat"], 6))


if __name__ == "__main__":
    main()
