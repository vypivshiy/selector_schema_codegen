import argparse
from pathlib import Path

# TODO
# 1 provide custom translators input


def _parse_arguments():
    parser = argparse.ArgumentParser(
        prog="Selector schema generator",
        description="Generate selector schemas from config file",
        usage="cli my_conf.yaml python out_file",
    )

    parser.add_argument("cfg", help="YAML config file path")
    parser.add_argument(
        "lang", choices=["python", "dart"], help="Programming language choice"
    )
    parser.add_argument(
        "-n",
        "--name",
        default="schema",
        help="schema filename output " "(default: schema + .extension)",
    )
    parser.add_argument(
        "-o",
        "--out",
        default=Path.cwd(),
        help="Output directory (default: current working directory)",
    )
    parser.add_argument(
        "-y",
        dest="OVERWRITE",
        default=Path.cwd(),
        action="store_true",
        help="Suggest overwrite file",
    )

    namespace = parser.parse_args()
    return namespace


def main():
    """CLI entrypoint"""
    from ssc_codegen.render import generate_code
    from ssc_codegen.yaml_parser import parse_config

    args = _parse_arguments()
    cfg_file = args.cfg
    programming_lang = args.lang
    output_dir = args.out
    output_filename = args.name

    if output_filename == "schema":
        match programming_lang:
            case "python":
                output_filename += ".py"
            case "dart":
                output_filename += ".dart"
            case _:
                print("Not supported, exit")
                exit(1)
    else:
        output_filename = output_dir / Path(output_filename)
    print(
        "Start generate code:",
        f"Config file: {cfg_file}",
        f"Prog lang: {programming_lang}",
        f"Output dir: {output_dir}/{output_filename}",
        sep="\n",
    )
    if Path(f"{output_dir}/{output_filename}").exists() and not args.OVERWRITE:
        choice = input("Overwrite? (y/n)?")
        if choice.lower() != "y":
            print("Cancel operation")
            exit(1)

    match programming_lang:
        case "python":
            from ssc_codegen.configs.python.python_parsel import Translator

            template = "python/python_any.j2"
        case "dart":
            from ssc_codegen.configs.dart.dart_html import Translator

            template = "dart/dart_html.j2"
        case _:
            print("Unknown prog lang, exit")
            exit(1)
    print("Generate code")
    cfg_info = parse_config(file=cfg_file, translator=Translator)
    code = generate_code(cfg_info, template)

    print(f"Write to {output_filename}")
    with open(output_filename, "w") as f:
        f.write(code)
    print("Done")


if __name__ == "__main__":
    main()
