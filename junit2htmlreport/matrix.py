"""
Handle multiple parsed junit reports
"""
from __future__ import unicode_literals

import os
import re
from junit2htmlreport import parser
from junit2htmlreport.parser import SKIPPED, FAILED, PASSED, ABSENT

UNTESTED = "untested"
PARTIAL_PASS = "partial pass"
PARTIAL_FAIL = "partial failure"
TOTAL_FAIL = "total failure"


def natural_sort_key(s, _nsre=re.compile('([0-9]+)')):
    return [int(text) if text.isdigit() else text.lower()
            for text in _nsre.split(s)]


class ReportMatrix(object):
    """
    Load and handle several report files
    """

    def __init__(self, prop_prefix=None, prop_count=0):
        self.reports = {}
        self.cases = {}
        self.classes = {}
        self.casenames = {}
        self.result_stats = {}
        self.properties = {}

        # Set up all properties in advance,
        # so we can tell which ones have tests, and which dont.
        if prop_prefix and prop_count:
            for i in range(1, prop_count + 1):
                self.properties[prop_prefix + str(i)] = []

    def report_order(self):
        return sorted(self.reports.keys())

    def property_order(self):
        return sorted(self.properties.keys(), key=natural_sort_key)

    def short_outcome(self, outcome):
        if outcome == PASSED:
            return "/"
        elif outcome == SKIPPED:
            return "s"
        elif outcome == FAILED:
            return "f"
        elif outcome == TOTAL_FAIL:
            return "F"
        elif outcome == PARTIAL_PASS:
            return "%"
        elif outcome == PARTIAL_FAIL:
            return "X"
        elif outcome == UNTESTED:
            return "U"

        return "?"

    def add_report(self, filename):
        """
        Load a report into the matrix
        :param filename:
        :return:
        """
        parsed = parser.Junit(filename=filename)
        filename = os.path.basename(filename)
        self.reports[filename] = parsed

        for suite in parsed.suites:
            for testclass in suite.classes:
                if testclass not in self.classes:
                    self.classes[testclass] = {}
                if testclass not in self.casenames:
                    self.casenames[testclass] = list()
                self.classes[testclass][filename] = suite.classes[testclass]

                for testcase in self.classes[testclass][filename].cases:
                    basename = testcase.basename().strip()
                    if basename not in self.casenames:
                        self.casenames[testclass].append(basename)

                    if testclass not in self.cases:
                        self.cases[testclass] = {}
                    if basename not in self.cases[testclass]:
                        self.cases[testclass][basename] = {}

                    self.cases[testclass][basename][filename] = testcase

                    outcome = testcase.outcome()
                    self.result_stats[outcome] = 1 + self.result_stats.get(
                        outcome, 0)

                    # For each SRS ID, add a column
                    for prop in testcase.properties:
                        # Assuming ALL properties are relevant
                        if prop.value not in self.properties:
                            print("WARNING: Ignoring unrecognized property: {}"
                                  .format(prop.value))
                            continue

                        self.properties[prop.value].append(testcase)
                        self.cases[testclass][basename][prop.value] \
                            = testcase

    def summary(self):
        """
        Render a summary of the matrix
        :return:
        """
        raise NotImplementedError()

    def combined_result(self, results):
        """
        Given a list of results, produce a "combined" overall result
        :param results:
        :return:
        """
        if PASSED in results:
            if FAILED in results:
                return self.short_outcome(PARTIAL_FAIL), PARTIAL_FAIL.title()
            if SKIPPED in results:
                return self.short_outcome(PARTIAL_PASS), PARTIAL_PASS.title()
            return self.short_outcome(PASSED), PASSED.title()

        if FAILED in results:
            return self.short_outcome(TOTAL_FAIL), TOTAL_FAIL.title()
        if SKIPPED in results:
            return self.short_outcome(UNTESTED), UNTESTED.title()
        return " ", ""


class HtmlReportMatrix(ReportMatrix, parser.HtmlHeadMixin):
    """
    Render a matrix report as html
    """

    def __init__(self, outdir, prop_prefix, prop_count):
        super(HtmlReportMatrix, self).__init__(
            prop_prefix=prop_prefix, prop_count=prop_count)
        self.outdir = outdir

    def add_report(self, filename):
        """
        Load a report
        """
        super(HtmlReportMatrix, self).add_report(filename)
        basename = os.path.basename(filename)
        # make the individual report too
        report = self.reports[basename].html()
        with open(os.path.join(self.outdir, basename) + ".html",
                  "w") as filehandle:
            filehandle.write(report)

    def get_stats_table(self):
        stats = "<table class='result-stats'>"
        for outcome in sorted(self.result_stats.keys()):
            stats += "<tr><th class='{}'>Tests {}<th>" \
                "<td align='right'>{}</td></tr>".format(
                    outcome,
                    outcome.title(),
                    self.result_stats[outcome]
                )
        stats += "</table>"
        return stats

    def short_outcome(self, outcome):
        if outcome == PASSED:
            return "ok"
        return super(HtmlReportMatrix, self).short_outcome(outcome)

    def summary(self):
        """
        Render the html
        :return:
        """

        # Keep track of whether each property had a successful test
        property_class = {}

        # iterate each class
        output = ''
        for classname in self.classes:
            # new class
            output += "<tr class='testclass'><td colspan='{}'>{}</td></tr>\n"\
                .format(len(self.properties) + 3, classname)

            # print the case name
            for casename in sorted(set(self.casenames[classname])):
                output += "<tr class='testcase'><td width='16'>{}</td>"\
                    .format(casename)

                case_results = []

                # print each test and its result for each axis
                celltds = ""
                for axis in self.property_order():
                    cellclass = ABSENT
                    anchor = None
                    if axis not in self.cases[classname][casename]:
                        cell = "&nbsp;"
                    else:
                        testcase = self.cases[classname][casename][axis]
                        anchor = testcase.anchor()

                        cellclass = testcase.outcome()
                        cell = self.short_outcome(cellclass)
                    case_results.append(cellclass)

                    # Assume only one report file
                    report_name = list(self.reports.keys())[0]
                    cell = "<a class='tooltip-parent testcase-link' href='{}.html#{}'>{}{}</a>".format(
                        report_name, anchor, cell,
                        "<div class='tooltip'>({}) {}</div>".format(
                            cellclass.title(),
                            axis)
                    )
                    if cellclass == ABSENT:
                        cell = ""

                    celltds += "<td class='testcase-cell {}'>{}</td>".format(
                        cellclass,
                        cell)

                    if property_class.get(axis) in [None, ABSENT]:
                        property_class[axis] = cellclass

                combined_name = self.combined_result(case_results)[1]

                output += celltds
                output += "<td span class='testcase-combined'>{}</td>".format(
                    combined_name
                )
                output += "</tr>"

        output += "</table>"
        output += "</body>"
        output += "</html>"

        # Header is done AFTER the body, in order to highlight properties
        # that have passing tests.
        header = self.get_html_head("")
        header += "<body>"
        header += "<h2>Reports Matrix</h2><hr size='1'/>"

        # table headers,
        #
        #          report 1
        #          |  report 2
        #          |  |  report 3
        #          |  |  |
        #   test1  f  /  s  % Partial Failure
        #   test2  s  /  -  % Partial Pass
        #   test3  /  /  /  * Pass
        header += "<table class='test-matrix'>"

        # def make_underskip(length):
        #     return "<td align='middle'>&#124;</td>" * length

        spansize = 1 + len(self.properties)
        report_headers = 0

        shown_stats = False

        stats = self.get_stats_table()
        header += "<tr>"

        for axis in self.property_order():
            label = axis
            if label.endswith(".xml"):
                label = label[:-4]
            # underskip = make_underskip(report_headers)

            # header = "<td colspan='{}'><pre>{}</pre></td>".format(spansize,
            #                                                       label)
            cell = "<td class='{}' colspan='1'><pre>{}</pre></td>"\
                .format(property_class.get(label, 'absent'), label)

            spansize -= 1
            report_headers += 1
            first_cell = ""
            if not shown_stats:
                # insert the stats table
                first_cell = "<td>{}</td>".format(
                    stats
                )
                header += first_cell
                shown_stats = True

            header += cell

        # output += "<tr><td></td>{}</tr>".format(
        #     make_underskip(len(self.properties)))
        header += "</tr>"
        return header + output


class TextReportMatrix(ReportMatrix):
    """
    Render a matrix report as text
    """

    def summary(self):
        """
        Render as a string
        :return:
        """

        output = "\nMatrix Test Report\n"
        output += "===================\n"

        axis = list(self.reports.keys())
        axis.sort()

        # find the longest classname or test case name
        left_indent = 0
        for classname in self.classes:
            left_indent = max(len(classname), left_indent)
            for casename in self.casenames[classname]:
                left_indent = max(len(casename), left_indent)

        # render the axis headings in a stepped tree
        treelines = ""
        for filename in self.property_order():
            output += "{}    {}{}\n".format(" " * left_indent, treelines,
                                            filename)
            treelines += "| "
        output += "{}    {}\n".format(" " * left_indent, treelines)
        # render in groups of the same class

        for classname in self.classes:
            # new class
            output += "{}  \n".format(classname)

            # print the case name
            for casename in sorted(set(self.casenames[classname])):
                output += "- {}{}  ".format(
                    casename, " " * (left_indent - len(casename)))

                # print each test and its result for each axis
                case_data = ""
                case_results = []
                for axis in self.property_order():
                    if axis not in self.cases[classname][casename]:
                        case_data += "  "
                    else:
                        testcase = self.cases[classname][casename][axis]
                        if testcase.skipped:
                            case_data += "s "
                            case_results.append(SKIPPED)
                        elif testcase.failure:
                            case_data += "f "
                            case_results.append(FAILED)
                        else:
                            case_data += "/ "
                            self.append = case_results.append(PASSED)

                combined, combined_name = self.combined_result(case_results)

                output += case_data
                output += " {} {}\n".format(combined, combined_name)

        # print the result stats

        output += "\n"
        output += "-" * 79
        output += "\n"

        output += "Test Results:\n"

        for outcome in sorted(self.result_stats):
            output += "  {:<12} : {:>6}\n".format(
                outcome.title(),
                self.result_stats[outcome])

        return output
