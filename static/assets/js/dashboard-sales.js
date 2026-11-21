(function () {
    function getColors(chartId) {
        var chart = document.getElementById(chartId);
        if (!chart) {
            return [];
        }

        var colors = JSON.parse(chart.getAttribute("data-colors") || "[]");
        return colors.map(function (color) {
            if (color.indexOf("var(") === 0) {
                var variableName = color.replace("var(", "").replace(")", "");
                return getComputedStyle(document.documentElement).getPropertyValue(variableName).trim();
            }
            return color;
        });
    }

    function renderLineChart() {
        var chartElement = document.querySelector("#todayCallsTrendChart");
        if (!chartElement || !window.ApexCharts) {
            return;
        }

        new ApexCharts(chartElement, {
            chart: {
                height: 330,
                type: "area",
                toolbar: { show: false }
            },
            series: [
                {
                    name: "Calls",
                    data: [64, 88, 112, 135, 154, 178, 160, 132, 146, 171]
                },
                {
                    name: "Lead Actions",
                    data: [28, 42, 56, 73, 88, 96, 82, 71, 76, 92]
                }
            ],
            colors: getColors("todayCallsTrendChart"),
            dataLabels: { enabled: false },
            stroke: { curve: "smooth", width: 3 },
            fill: {
                type: "gradient",
                gradient: {
                    shadeIntensity: 0.3,
                    opacityFrom: 0.35,
                    opacityTo: 0.06,
                    stops: [0, 90, 100]
                }
            },
            xaxis: {
                categories: ["9 AM", "10 AM", "11 AM", "12 PM", "1 PM", "2 PM", "3 PM", "4 PM", "5 PM", "6 PM"]
            },
            yaxis: {
                labels: {
                    formatter: function (value) {
                        return Math.round(value);
                    }
                }
            },
            grid: {
                borderColor: "#eee9ff",
                strokeDashArray: 4
            },
            legend: {
                position: "top",
                horizontalAlign: "right"
            }
        }).render();
    }

    function renderDonutChart() {
        var chartElement = document.querySelector("#callTypeChart");
        if (!chartElement || !window.ApexCharts) {
            return;
        }

        new ApexCharts(chartElement, {
            chart: {
                height: 330,
                type: "donut"
            },
            series: [930, 318],
            labels: ["Outgoing", "Incoming"],
            colors: getColors("callTypeChart"),
            legend: {
                position: "bottom"
            },
            dataLabels: {
                formatter: function (value) {
                    return value.toFixed(1) + "%";
                }
            },
            plotOptions: {
                pie: {
                    donut: {
                        size: "68%",
                        labels: {
                            show: true,
                            total: {
                                show: true,
                                label: "Total Calls",
                                formatter: function () {
                                    return "1248";
                                }
                            }
                        }
                    }
                }
            }
        }).render();
    }

    function renderPaymentChart() {
        var chartElement = document.querySelector("#paymentTargetChart");
        if (!chartElement || !window.ApexCharts) {
            return;
        }

        new ApexCharts(chartElement, {
            chart: {
                height: 315,
                type: "radialBar"
            },
            series: [72.6],
            colors: getColors("paymentTargetChart"),
            plotOptions: {
                radialBar: {
                    hollow: { size: "62%" },
                    dataLabels: {
                        name: {
                            show: true,
                            offsetY: 22,
                            color: "#74788d",
                            fontSize: "13px"
                        },
                        value: {
                            offsetY: -12,
                            fontSize: "28px",
                            fontWeight: 700,
                            formatter: function (value) {
                                return value.toFixed(1) + "%";
                            }
                        }
                    }
                }
            },
            labels: ["Rs 8.72L / Rs 12L"]
        }).render();
    }

    function renderTopEmployeeChart() {
        var chartElement = document.querySelector("#topEmployeeSalesChart");
        if (!chartElement || !window.ApexCharts) {
            return;
        }

        new ApexCharts(chartElement, {
            chart: {
                height: 315,
                type: "bar",
                toolbar: { show: false }
            },
            series: [{
                name: "Sales",
                data: [2.30, 1.95, 1.28, 1.12, 0.82]
            }],
            colors: getColors("topEmployeeSalesChart"),
            plotOptions: {
                bar: {
                    borderRadius: 5,
                    horizontal: true,
                    barHeight: "55%"
                }
            },
            dataLabels: {
                enabled: true,
                formatter: function (value) {
                    return "Rs " + value.toFixed(2) + "L";
                }
            },
            xaxis: {
                categories: ["Amit", "Rohan", "Neha", "Ajay", "Kiran"],
                labels: {
                    formatter: function (value) {
                        return "Rs " + value + "L";
                    }
                }
            },
            grid: {
                borderColor: "#eee9ff",
                strokeDashArray: 4
            }
        }).render();
    }

    function renderRoleChart(chartId, categories, values) {
        var chartElement = document.querySelector("#" + chartId);
        if (!chartElement || !window.ApexCharts) {
            return;
        }

        new ApexCharts(chartElement, {
            chart: {
                height: 235,
                type: "bar",
                sparkline: { enabled: false },
                toolbar: { show: false }
            },
            series: [{
                name: "Today Sales",
                data: values
            }],
            colors: getColors(chartId),
            plotOptions: {
                bar: {
                    borderRadius: 5,
                    columnWidth: "45%"
                }
            },
            dataLabels: {
                enabled: false
            },
            xaxis: {
                categories: categories
            },
            yaxis: {
                labels: {
                    formatter: function (value) {
                        return value + "L";
                    }
                }
            },
            tooltip: {
                y: {
                    formatter: function (value) {
                        return "Rs " + value.toFixed(2) + "L";
                    }
                }
            },
            grid: {
                borderColor: "#eee9ff",
                strokeDashArray: 4
            }
        }).render();
    }

    renderLineChart();
    renderDonutChart();
    renderPaymentChart();
    renderTopEmployeeChart();
    renderRoleChart("baPerformanceChart", ["Amit", "Ajay", "Suresh", "Pooja"], [2.30, 1.12, 0.94, 0.88]);
    renderRoleChart("sbaPerformanceChart", ["Rohan", "Meera", "Nitin", "Farah"], [1.95, 1.34, 1.10, 0.98]);
    renderRoleChart("taPerformanceChart", ["Kiran", "Vikas", "Ramesh", "Divya"], [0.82, 0.74, 0.62, 0.58]);
})();
