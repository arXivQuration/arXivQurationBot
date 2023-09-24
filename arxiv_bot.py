import datetime
import os
import typing

import arxiv
import deepl
from dotenv import load_dotenv
from github import Auth, Github, GithubIntegration

def get_private_key() -> str:
    if (key := os.environ.get("GH_APPKEY")):
        return key
    with open(".secret/arxivqurationbot.2023-07-02.private-key.pem", "r") as f:
        return f.read()


def get_github_instance() -> Github:
    key = get_private_key()
    auth = Auth.AppAuth(int(os.environ["GH_APPID"]), key)
    gi = GithubIntegration(auth=auth)
    installations = gi.get_installations()
    return installations[0].get_github_for_installation()


def compose_authors_markdown(authors: list[arxiv.Result.Author]) -> str:
    return ", ".join(author.name for author in authors)


def compose_links_markdown(entry: arxiv.Result) -> str:
    abs_url = entry.entry_id
    ar5iv_url = abs_url.replace("arxiv", "ar5iv")
    
    def link_to_markdown(link: arxiv.Result.Link) -> str | None:
        if link.title == "doi" and entry.doi and (entry.doi in link.href):
            return None
        if link.href in [abs_url, entry.pdf_url]:
            return None
        if link.title:
            return f"[{link.title}]({link.href})"
        return link.href

    markdowns = [abs_url, f"[ar5iv]({ar5iv_url})"]
    if (pdf_url := entry.pdf_url):
        markdowns.append(f"[pdf]({pdf_url})")

    markdowns += [md for link in entry.links if (md := link_to_markdown(link))]
    
    s = markdowns[0]
    s += f' ({", ".join(markdowns[1:])})'

    if entry.doi:
        s += f"\n[doi:{entry.doi}](https://doi.org/{entry.doi})"
        
    return s


def compose_body(summary_ja: str, links: str, authors: str, published: datetime.datetime) -> str:
    published_str = published.strftime("%Y/%m/%d")
    return f"""# Summary (DeepL訳)
{summary_ja}

## Links
{links}

## Authors
{authors}

## Published
{published_str}"""


if __name__ == "__main__":
    load_dotenv()

    today = datetime.date.today()
    date_from = (today - datetime.timedelta(days=6)).strftime("%Y%m%d")
    date_to = (today - datetime.timedelta(days=5)).strftime("%Y%m%d")

    DEEPL_AUTHKEY = os.environ["DEEPL_AUTHKEY"]
    translator = deepl.Translator(DEEPL_AUTHKEY)
    gh = get_github_instance()
    repo = gh.get_repo("arXivQuration/arXivQurationBot")

    query = f'cat:quant-ph AND submittedDate:[{date_from} TO {date_to}] AND ("quantum comput" OR qubit)'

    for result in arxiv.Search(query=query, max_results=50).results():
        title = result.title
        authors = compose_authors_markdown(result.authors)
        links = compose_links_markdown(result)
        summary_en = result.summary.replace('\n', ' ')
        translate_result = translator.translate_text(result.summary.replace('\n', ' '), target_lang="JA")
        summary_ja = typing.cast(deepl.translator.TextResult, translate_result).text
        body = compose_body(summary_ja=summary_ja, links=links, authors=authors, published=result.published)
        repo.create_issue(title=title, body=body)
