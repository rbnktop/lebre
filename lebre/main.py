print("\n" *35)
from rich import print, inspect
from rich.console import Console
import sys

console = Console()
console.print((f"\n:mage: Welcome!:parrot:\n\n"),justify='center')
console.print(f"\n"*12)
import time
from rich.panel import Panel


def main():
    with console.status("[bold blue]System initializing...\n", spinner="earth") as status:
        
        status.update("[bold blue]Loading heavy engines (Pandas/RapidFuzz)...")
        from wuzzy import Core
        
        status.update("[bold blue]Connecting to data sources...")
        engine = Core('data.xlsx', 'abbreviations.json', 'lista.txt')
        time.sleep(0.2)

        status.update("[bold yellow]Reading Excel sheets...")
        raw_sheet, raw = engine.read_sheet()
        time.sleep(0.2)

        status.update("[bold magenta]Cleaning data & applying rules...")
        filtered_df = engine.process_sheet(raw_df=raw_sheet)
        time.sleep(0.2)

        status.update("[bold green3]Initilizaing fuzz")
        time.sleep(0.2)

    # threshold = int(console.input("\n:mage: Select a threshold [red]0[/]-[green1]100[/]\n:backhand_index_pointing_right: "))
    clean_data, stats = engine.fuz(data=filtered_df, threshold=94)
    del filtered_df

    summary = (
        f"[grey]Items Parsed:         {raw}[/]\n"
        f"[yellow]Filtered Items:       {stats['original']}[/]\n"
        f"[red]Duplicates Removed:   {stats['dropped']}[/]\n"
        f"[bold chartreuse1]Final Clean Items:    {stats['final']}[/]"
    )
    
    console.print()
    console.print(Panel(summary, title="[gray15]DEDUPLICATION SUMMARY", expand=False, border_style="gray11"),justify='center')
    result, analytics, n_targets = engine.sec_fuz(clean_data)

    analytic = (
        f"Number of items: {n_targets}\n"
        f"Items with no match: {analytics}"
    )
    console.print(f"\n"*3)
    console.print(Panel(analytic, title="[gray15]LIST ANALYSIS", expand=False, border_style="gray11"),justify='center')


    engine.review(result)
    print (f"\n"*3)
    console.print((":mage: GoodBye!:parrot:"),justify='center')
    print (f"\n"*4)
    console.print((":cigarette: cabelo ltda"),justify='right')


if __name__ == "__main__":
    try:
       main()
    except Exception as e:
        print(f" error_main: {e}")
        sys.exit(1)
    finally:
        sys.exit(0)