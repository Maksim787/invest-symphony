from dataclasses import dataclass
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .portfolio import Portfolio, Bond, Stock


@dataclass
class Graphs:
    pie_chart: str
    cum_return_chart: str = None


def add_trace_for_pie_chart(fig, instruments: list[Bond | Stock], graph_number: int):
    total_capital = sum(instrument.invested_capital for instrument in instruments)
    sector_percentages = [(instrument.sector, instrument.invested_capital / total_capital * 100) for instrument in instruments]
    labels, sizes = zip(*sector_percentages)
    fig.add_trace(go.Pie(labels=labels, values=sizes), 1, graph_number)


def create_pie_chart(portfolio: Portfolio):
    n_pies = bool(portfolio.stocks) + bool(portfolio.bonds)
    if n_pies == 0:
        return ''
    fig = make_subplots(rows=1, cols=n_pies, specs=[[{'type': 'domain'}] * n_pies])

    annotations = []
    if portfolio.stocks:
        add_trace_for_pie_chart(fig, portfolio.stocks, min(1, n_pies))
        annotations += [dict(text='Акции', x=0.18 if portfolio.bonds else 0.5, y=0.5, font_size=20, showarrow=False)]
    if portfolio.bonds:
        add_trace_for_pie_chart(fig, portfolio.bonds, min(2, n_pies))
        annotations += [dict(text='Облигации', x=0.82 if portfolio.stocks else 0.5, y=0.5, font_size=20, showarrow=False)]

    fig.update_traces(hole=0.4, hoverinfo="label+percent")
    fig.update_layout(title="Распределение по секторам", annotations=annotations)

    return fig.to_html(include_plotlyjs='cdn', full_html=False)


def create_graphs(portfolio: Portfolio) -> Graphs:
    """
    Make graphs of the portfolio
    """
    return Graphs(pie_chart=create_pie_chart(portfolio))
