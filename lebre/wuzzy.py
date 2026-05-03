import functools
import openpyxl
import pandas as pd
from rapidfuzz import fuzz
from datetime import datetime
from itertools import combinations
import unicodedata
from rich import print
from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.console import Console
import re
import sys
from models import MatchCandidate, MultiMatchResult
import pyperclip

console = Console()


def func_handler(func):
    "decorator to handle try and except blocks"
    @functools.wraps(func)

    def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
        
            except Exception as e:
                return f"@func_handler_{func.__name__()} error: {e}"
    return wrapper

class Core():
    def __init__(self, data, rules, items):
        self.data = pd.read_excel(data, header=None).dropna(axis=1, how='all')
        self.rules = pd.read_json(rules, typ='series').to_dict()

        with open(items, 'r', encoding='utf-8') as f:
            self.items: list[str] = f.read().splitlines()
        
    @func_handler
    def standardstr(self, raw_str):
        """
        takes a str and removes all the "ç, ñ" characters, normalizing them 
        into a standard str for better and precise comparsion. 
        a nice method to achieve so its encoding the str to ascii, making sure only the 
        basic characters are allowed, then decoding it back to utf-8 for further processing
        """
        return unicodedata.normalize('NFD', raw_str).encode('ascii', 'ignore').decode('utf-8').lower().strip()
    
    @func_handler
    def numb_dif(self, num_x, num_y):
        """
        fuzz() was giving a high score to candidates having different integers in it
        eg. coca-cola 350ml, coca-cola 700ml. 
        this was dangerous, and my approach to prevent this matches was checking beforehand if both
        items had the same numbers in it.
        using a regular expression was the best way to achieve so.
        r for raw string, (backslash)d = digits and + means keeping the int integrity
        turning the result found into a set makes it faster apparently and
        even tho a set deduplicates items, this isnt a problem for the data we are manipulating.
        """
        num_x = set(re.findall(r'\d+', (num_x)))
        num_y = set(re.findall(r'\d+', (num_y)))

        return num_x != num_y
    
    @func_handler  
    def read_sheet(self):
        """
        i didnt want to create a giant function block to manipulate the .xlsx data so i divided it into steps
        first we melt dates to the items. doing so we get some valuable methods like groupby().max()
        which previously would take too long looking every single cell and compare to the column
        basically it stripped down every item into a giant column containing dates/items with respect to their dates
        which makes it easier for engines to work. it wasnt meant for humans, god knows i learned it the hard way
        """

        df = self.data
        dates = df.iloc[0]
        # specifying that dates will always be the first row
        
        items = df.iloc[1:]
        # and the items will be the following rows
        
        items.columns = dates
        # setting the first rows as date headers
        
        df_melted = items.melt(var_name='Date', value_name='Item')
        # melting the items into the dates headers
        
        df_melted['Date'] = pd.to_datetime(df_melted['Date'], errors='coerce', dayfirst = True)
        # using pandas .to_datetime method to convert the columns allowing them to sort with .max() method 
        # without this it would simply be a str for the program, and therefore unable to be sorted
        
        df_melted = df_melted.dropna(subset=['Date', 'Item'])
        # emptying rows that doesnt exist

        raw = len(df_melted['Item'])
        del df
        return df_melted, raw

    @func_handler
    def process_sheet(self, raw_df):
        """
        now for the filtering, sorting by date part.

        >items like: 5Fralda Pampers C/ 12unidades
        >becomes: 5 fralda pampers com 12 un
        this greatly improves the precision for comparsion

        """
        df = raw_df

        df['Item'] = df['Item'].apply(self.standardstr)
        # standardize items strings removing ~ and ç turning them lowercase
        # for convenience and precise comparsion

        df['Item'] = df['Item'].str.replace(r'[^a-zA-Z0-9 ]', '', regex=True)
        # removing anything thats not letters and numbers eg. "/"
    
        df['Item'] = df['Item'].str.replace(r'(\d+)([a-zA-Z]+)', r'\1 \2', regex=True)
        df['Item'] = df['Item'].str.replace(r'([a-zA-Z]+)(\d+)', r'\1 \2', regex=True)
        # ungluing the numbers from the strings eg. 350ml > 350 ml

        df['Item'] = df['Item'].replace(self.rules, regex=True)
        # replacing abbreviations for the previous reason as well

        df['Item'] = df['Item'].str.strip().str.replace(r'\s+', ' ', regex=True)
        # removing blank spaces in between them

        result = df.groupby('Item')['Date'].max().to_dict()
        # sorting and merging the items with the same name prioritizing the recent date.
        # not even needing to use the rapidfuzz lib yet :)
        ## the method .max(), to keep the most recent date automatically, creates an index for each item for some reason
        ## so i had to reset it back so i could make a dictionary with no problems
        # debugging i just learned that zipping the df by itself without this line still removed duplicates but
        # if i havent sorted it wouldve been a unorganized mess and the zipping wouldve messed the logic
        
        # final_df['Date'] = final_df['Date'].dt.strftime('%d/%m/%Y')
        # converting the date back for convenience
        
        # result = dict(zip(final_df['Item'], final_df['Date']))
        # del final_df
        # converting the data into a dictionary.

        del df
        return result

    @func_handler
    def fuz(self, data, threshold):
        """
        Compares every item looking for fuzzy duplicates.
        Because data is sorted newest->oldest, the first item in a match is kept,
        and the second item is flagged for removal.
        """

        items_to_drop = set()
        pairs = list(sorted(data.items(), key=lambda x: x[1], reverse=True))
        
        n = len(pairs)
        total_combinations = (n * (n - 1)) // 2

        with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=None), 
        TimeElapsedColumn(),
        TaskProgressColumn(),
        expand=True,
        transient=True,
        refresh_per_second=60,
        ) as progress:

            task = progress.add_task(":mag: Filtering data...", total=total_combinations)

            for (item_x, date_x), (item_y, date_y) in combinations(pairs, 2):
                progress.advance(task)
                if item_x in items_to_drop or item_y in items_to_drop:
                    continue
                
                if self.numb_dif(item_x, item_y):
                    continue
                
                score = fuzz.token_sort_ratio(item_x, item_y)

                if score >= threshold:
                    items_to_drop.add(item_y)
                    # print(f"\n [red]Dropping:[/] {item_y} {date_y.strftime('%d/%m')}\n>[dim] {int(score)} Kept: {item_x} {date_x.strftime('%d/%m')}[/]")
                
                # elif score < threshold and  score > 85:
                #     print(f"\n [red dim]NOT DROP:[/] {item_y} {date_y.strftime('%d/%m')}\n>[dim] {int(score)} Kept: {item_x} {date_x.strftime('%d/%m')}[/]")


        # This keeps only the items that did NOT end up in the drop set
        final_clean_data = {k: v for k, v in data.items() if k not in items_to_drop}

        stats = {
            "original": len(data),
            "dropped": len(items_to_drop),
            "final": len(final_clean_data)
        }
        
        return final_clean_data, stats

    @func_handler
    def list_to_df(self):
        """
        sorting the target list using pandas dataframe
        """
        df = pd.DataFrame(self.items, columns=['Targets'])

        df['Targets'] = df['Targets'].apply(self.standardstr)
        df['Targets'] = df['Targets'].str.replace(r'[^a-zA-Z0-9 ]', '', regex=True)
        df['Targets'] = df['Targets'].str.replace(r'(\d)([a-zA-Z])', r'\1 \2', regex=True)
        df['Targets'] = df['Targets'].str.replace(r'([a-zA-Z])(\d)', r'\1 \2', regex=True)
        df['Targets'] = df['Targets'].replace(self.rules, regex=True)
        df['Targets'] = df['Targets'].str.strip().str.replace(r'\s+', ' ', regex=True)

        clean_list = df['Targets'].tolist()
        
        return clean_list
    @func_handler
    def sec_fuz(self, candidates):
        """
        a function to find the items in target inside the clean deduplicated dataframe candidates
        """

        targets = list(self.list_to_df())
        sorted_candidates = dict(sorted(candidates.items(), key=lambda x: x[1], reverse=True))
        best_candidates:list = []
        results:list = []
        print(f"\n"*4)

        with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=None), 
        TaskProgressColumn(),
        expand=True,
        transient=True,
        refresh_per_second=60,
        ) as progress:
            task = progress.add_task(":mag: Comparing candidates...", total=len(targets))

            for tgt in targets:
                best_candidates:list = []
                # print(f"\n >[white] {tgt} [/]< ")

                for candidate_name, candidate_date in sorted_candidates.items():
                    if self.numb_dif(tgt, candidate_name):
                        continue

                    score = fuzz.token_sort_ratio(tgt, candidate_name)
                    candidate_date = candidate_date.to_pydatetime()

                    if score >= 98:
                        best_candidates = [MatchCandidate(candidate_name = candidate_name, candidate_date = candidate_date, candidate_score = score)]
                        # print(f"[green]{int(score)}%[/] {candidate_name} [green]{candidate_date.strftime('%d/%m/%y')}[/]")
                        break

                    elif score >= 75:
                        best_candidates.append(MatchCandidate(candidate_name=candidate_name, candidate_date=candidate_date, candidate_score=score))
                        #  print(f"[orange3]{int(score)}%[/] {candidate_name} [orange3]{candidate_date.strftime('%d/%m/%y')}[/]")
                    
                    progress.advance(task)
                best_candidates.append(MatchCandidate(candidate_name='None', candidate_date=datetime(1996, 7, 1), candidate_score=0))
                best_candidates = best_candidates[:5]
                results.append(MultiMatchResult(target_name=tgt, candidates=best_candidates))

                # analytics = 0
                # for res in results:
                #     for c in res.candidates:
                #         if c.candidate_name == 'None':
                #             analytics +=1
                    
        n_targets = len(targets)
        return results, n_targets
    
    @func_handler
    def review(self, results):
        """
        reviewing the correct candidates
        """

        console.print((f" :mage: Review:parrot:"),justify='center')
        print(f'\n'*2)
        console.print((f" do you want to review the candidates ?:parrot: \n[PRESS ENTER]"), justify='center')
        print(f'\n')
        console.print((f" :mage: or do you want the program to automatically choose the best candidates? \n[PRESS 0]"), justify='center')
        print(f'\n'*4)

        if console.input(f" :parrot:> ") == '0':
            autom = True
        else:
            autom = False

        if not autom :
            print(f"\n"*15)
            console.print((f" :mage: Review:parrot:"),justify='center')
            print(f'\n'*3)
            console.print((f" :ringed_planet:  pressing enter selects the first candidate "), justify='center')
            console.print((f" :cross_mark:  target with [bright_red]no candidates[/] gets trashed automatically! "), justify='center')
            console.print((f" :heavy_check_mark:  candidates with [green1]>98% match[/] gets selected automatically "), justify='center')

        result = []
        minus = 0
        auto = 0
        for i in results:
            " for each item with its target name and candidates"
            left = len(results) - minus

            console.print(f"\n"*18)
            console.print((f" :mage: [ [blue3]{i.target_name}[/] ] "), justify='center')
            console.print(f"\n"*2)

            for e, c in enumerate(i.candidates):
                """
                create an index choice for each candidate so it can be manually selected
                """
                if c.candidate_name == 'None':
                    console.print((f" :backhand_index_pointing_right: [{e}] - skip "), justify='center')
                else:
                    console.print((f" :backhand_index_pointing_right: [{e}] - {c} "), justify='center')

            if i.candidates[0].candidate_score >= 98 or autom:
                """
                if candidate highscore auto selected
                """
                selected = i.candidates[0].candidate_date.strftime('%d/%m/%y')
                console.print((f"\n :heavy_check_mark:  {i.candidates[0]} "), justify='center')
                auto += 1

            elif i.candidates[0].candidate_name == 'None':
                """
                if invalid candiate auto discard
                """
                selected = 'Foto'
                console.print((f"\n :cross_mark: skip "), justify='center')
                auto += 1

            else:
                console.print(f"\n"*6)
                console.print(f" :cigarette:[dim] {left} candidates  left[/]")
                choice = console.input((f" :parrot: Select an index > "))
                console.print('\n')

                if choice.isdigit():
                    """
                    if valid choice proceed
                    """
                    index = int(choice)

                    if i.candidates[index].candidate_name == 'None':
                        """
                        this a "skip" workaround for when the user judges the review candidates as invalids
                        """
                        selected = 'Foto'
                        console.print ((f" :cross_mark: skip "), justify='center')
                        
                    else:
                        """
                        selecting the desired candidate for final result
                        """
                        selected = i.candidates[index].candidate_date.strftime('%d/%m/%y')
                        console.print ((f" :heavy_check_mark:  {i.candidates[index]} "), justify='center')

                else:
                    """
                    no digit selected, enter auto selects the first candidate
                    """
                    selected = i.candidates[0].candidate_date.strftime('%d/%m/%y')
                    console.print ((f" :heavy_check_mark:  {i.candidates[0]} "), justify='center')


            "appending the selected candidates to a list for extraction"
            result.append(selected)
            minus += 1

        data = "\n".join(result)
        pyperclip.copy(data)
        console.print(f"\n"*30)

        console.print((f":ringed_planet:  [dim]{auto} out of {len(results)} items were selected automatically in this session[/]  :ringed_planet:"),justify='center')
        console.print((f"\n:floppy_disk: Saved to Clipboard :cloud:\n"), justify='center')}
        
