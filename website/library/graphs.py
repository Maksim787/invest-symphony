from dataclasses import dataclass
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .portfolio import Portfolio, DataRAM


@dataclass
class Graphs:
    pie_chart: str
    cum_return_chart: str = None


def create_pie_chart(portfolio: Portfolio):
    total_stock_capital = sum(stock.invested_capital for stock in portfolio.stocks)
    total_bond_capital = sum(bond.invested_capital for bond in portfolio.bonds)

    stock_sector_percentages = [(stock.sector, stock.invested_capital / total_stock_capital * 100) for stock in portfolio.stocks]
    bond_sector_percentages = [(bond.sector, bond.invested_capital / total_bond_capital * 100) for bond in portfolio.bonds]

    stock_labels, stock_sizes = zip(*stock_sector_percentages)
    bond_labels, bond_sizes = zip(*bond_sector_percentages)

    fig = make_subplots(rows=1, cols=2, specs=[[{'type': 'domain'}, {'type': 'domain'}]])

    fig.add_trace(go.Pie(labels=stock_labels, values=stock_sizes, name="Stocks"), 1, 1)
    fig.add_trace(go.Pie(labels=bond_labels, values=bond_sizes, name="Bonds"), 1, 2)

    fig.update_traces(hole=0.4, hoverinfo="label+percent")
    fig.update_layout(title="Распределение по секторам", annotations=[dict(text='Акции', x=0.18, y=0.5, font_size=20, showarrow=False),
                                                                      dict(text='Облигации', x=0.82, y=0.5, font_size=20, showarrow=False)])
    return fig.to_html(include_plotlyjs='cdn', full_html=False)


def create_graphs(portfolio: Portfolio) -> Graphs:
    """
    Make graphs of the portfolio
    """
    return Graphs(pie_chart=create_pie_chart(portfolio))
