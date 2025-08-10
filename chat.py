import dns.resolver
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel

console = Console()

def encode_query(q: str) -> str:
    # Replace spaces with dots — valid DNS format
    return q.strip().replace(' ', '.')

def query_txt(domain: str, server: str = 'ch.at') -> list[str]:
    resolver = dns.resolver.Resolver(configure=True)
    resolver.nameservers = [dns.resolver.get_default_resolver().nameservers[0]]  # default DNS
    
    # Override DNS server if user wants custom server
    if server:
        # Try to resolve server to IP if needed
        try:
            answer = dns.resolver.resolve(server)
            ip = answer[0].to_text()
            resolver.nameservers = [ip]
        except Exception:
            # fallback: maybe server is IP already
            resolver.nameservers = [server]

    query_name = encode_query(domain)
    try:
        answers = resolver.resolve(query_name, 'TXT')
        # Extract strings from TXT records
        txts = []
        for rdata in answers:
            txts.extend([txt.decode() if isinstance(txt, bytes) else txt for txt in rdata.strings])
        return txts
    except Exception as e:
        return [f"[red]Error:[/] {e}"]

def main():
    console.print(Panel("[bold cyan]Welcome to Chat DNS TXT Query CLI[/bold cyan]\nType your DNS query below (e.g. 'what is golang')\nType 'exit' or Ctrl+C to quit", title="chat"))
    
    while True:
        try:
            user_query = Prompt.ask("[green]Enter query[/green]").strip()
            if user_query.lower() in ('exit', 'quit'):
                console.print("[yellow]Bye![/yellow]")
                break

            server = Prompt.ask("[blue]DNS Server[/blue]", default="ch.at").strip()
            results = query_txt(user_query, server)
            
            if results:
                console.print(Panel("\n".join(results), title=f"TXT Results for [bold]{user_query}[/bold] @ {server}", expand=False))
            else:
                console.print("[red]No TXT records found.[/red]")

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted, exiting...[/yellow]")
            break
        except Exception as ex:
            console.print(f"[red]Unexpected error:[/] {ex}")

if __name__ == '__main__':
    main()
