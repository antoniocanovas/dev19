import { loadBundle } from "@web/core/assets";
import { registry } from "@web/core/registry";
import { formatFloat } from "@web/views/fields/formatters";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

import { Component, onWillStart, onWillUnmount, useEffect, useRef } from "@odoo/owl";

const CHARTS = ["week", "month", "year", "debt"];

/**
 * Charts of the management dashboard (field chart_data of mercas.management.dashboard): the
 * week day by day, the month and the year accumulated, against the periods before and last
 * year, and the debt of the customers by age. Only in the backend: the summary sent by mail
 * keeps its charts made of tables.
 */
export class MercasManagementCharts extends Component {
    static template = "mercas_base.ManagementCharts";
    static props = { ...standardFieldProps };

    setup() {
        this.canvases = Object.fromEntries(CHARTS.map((name) => [name, useRef(name)]));
        this.charts = [];
        onWillStart(() => loadBundle("web.chartjs_lib"));
        useEffect(
            () => {
                this.renderCharts();
                return () => this.destroyCharts();
            },
            () => [this.data]
        );
        onWillUnmount(() => this.destroyCharts());
    }

    get data() {
        return this.props.record.data[this.props.name];
    }

    get hasDebt() {
        return this.data.debt.data.some((amount) => amount > 0);
    }

    destroyCharts() {
        this.charts.forEach((chart) => chart.destroy());
        this.charts = [];
    }

    money(value) {
        const { symbol, position } = this.data.currency;
        const amount = formatFloat(value, { digits: [69, 2] });
        return position === "before" ? `${symbol} ${amount}` : `${amount} ${symbol}`;
    }

    shortMoney(value) {
        const { symbol, position } = this.data.currency;
        const amount = formatFloat(value, { humanReadable: true, decimals: 0 });
        return position === "before" ? `${symbol} ${amount}` : `${amount} ${symbol}`;
    }

    /** Options of the bar and line charts: amounts on the axis and the tooltips. */
    commonOptions() {
        return {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { position: "bottom", labels: { boxWidth: 12 } },
                tooltip: {
                    callbacks: {
                        label: (item) =>
                            item.raw === null ? null : `${item.dataset.label}: ${this.money(item.raw)}`,
                    },
                },
            },
            scales: {
                y: { beginAtZero: true, ticks: { precision: 0, callback: (value) => this.shortMoney(value) } },
                x: { grid: { display: false } },
            },
        };
    }

    dataset(serie, type) {
        const color = this.data.colors[serie.key];
        return {
            label: serie.label,
            data: serie.data,
            backgroundColor: type === "line" ? color + "22" : color,
            borderColor: color,
            borderWidth: type === "line" ? (serie.key === "now" ? 3 : 2) : 0,
            borderRadius: type === "bar" ? 4 : 0,
            pointRadius: 0,
            pointHoverRadius: 4,
            tension: 0.25,
            fill: type === "line" && serie.key === "now",
            order: serie.key === "now" ? 0 : 1,
        };
    }

    /** Dashed line from the sales up to today to the forecast of the close. */
    forecastDataset(forecast, length) {
        const data = new Array(length).fill(null);
        data[forecast.from[0] - 1] = forecast.from[1];
        data[forecast.to[0] - 1] = forecast.to[1];
        return {
            label: forecast.label,
            data,
            borderColor: this.data.colors.now,
            borderDash: [6, 4],
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 4,
            spanGaps: true,
            fill: false,
        };
    }

    renderCharts() {
        this.destroyCharts();
        if (!this.data) {
            return;
        }
        const Chart = window.Chart;
        const { Info } = luxon;
        const { week, month, year, debt } = this.data;

        this.charts.push(
            new Chart(this.canvases.week.el, {
                type: "bar",
                data: {
                    labels: Info.weekdays("short"),
                    datasets: week.series.map((serie) => this.dataset(serie, "bar")),
                },
                options: this.commonOptions(),
            })
        );

        const monthLabels = Array.from({ length: month.days }, (_, index) => String(index + 1));
        this.charts.push(
            new Chart(this.canvases.month.el, {
                type: "line",
                data: {
                    labels: monthLabels,
                    datasets: [
                        ...month.series.map((serie) => this.dataset(serie, "line")),
                        this.forecastDataset(month.forecast, month.days),
                    ],
                },
                options: this.commonOptions(),
            })
        );

        this.charts.push(
            new Chart(this.canvases.year.el, {
                type: "line",
                data: {
                    labels: Info.months("short"),
                    datasets: [
                        ...year.series.map((serie) => this.dataset(serie, "line")),
                        this.forecastDataset(year.forecast, 12),
                    ],
                },
                options: this.commonOptions(),
            })
        );

        if (!this.hasDebt) {
            return;
        }
        this.charts.push(
            new Chart(this.canvases.debt.el, {
                type: "doughnut",
                data: {
                    labels: debt.labels,
                    datasets: [{ data: debt.data, backgroundColor: debt.colors, borderWidth: 1 }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: "60%",
                    plugins: {
                        legend: { position: "right", labels: { boxWidth: 12 } },
                        tooltip: {
                            callbacks: { label: (item) => `${item.label}: ${this.money(item.raw)}` },
                        },
                    },
                },
            })
        );
    }
}

registry.category("fields").add("mercas_management_charts", {
    component: MercasManagementCharts,
    supportedTypes: ["json"],
});
