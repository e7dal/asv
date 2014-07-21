# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os

import six

from . import Command
from .run import Run

from ..console import log, truncate_left, color_print
from ..repo import get_repo
from .. import results
from .. import util


class Continuous(Command):
    @classmethod
    def setup_arguments(cls, subparsers):
        parser = subparsers.add_parser(
            "continuous", help=
            "Run a side-by-side comparison of two commits for continuous "
            "integration.")

        parser.add_argument(
            'branch', nargs=1, default='master',
            help="""The HEAD branch to test.  This commit and its
            parent commit will be used as the two commits for
            comparison.""")
        parser.add_argument(
            '--factor', "-f", nargs='?', type=float, default=2.0,
            help="""The factor above or below which a result is
            considered problematic.  For example, with a factor of 2,
            if a benchmark gets twice as slow or twice as fast, it
            will be displayed in the results list.""")
        parser.add_argument(
            "--bench", "-b", type=str, nargs="*",
            help="""Regular expression(s) for benchmark to run.  When
            not provided, all benchmarks are run.""")
        parser.add_argument(
            "--machine-defaults", action="store_true",
            help="""Use autogenerated defaults for the machine information,
            instead of using the .asv-machine.json file""")

        parser.set_defaults(func=cls.run_from_args)

        return parser

    @classmethod
    def run_from_conf_args(cls, conf, args):
        return cls.run(
            conf=conf, branch=args.branch[0], factor=args.factor,
            bench=args.bench, machine_defaults=args.machine_defaults
        )

    @classmethod
    def run(cls, conf, branch="master", factor=2.0, bench=None,
            machine_defaults=False):
        repo = get_repo(conf)

        repo.checkout_remote_branch('origin', branch)
        head = repo.get_hash_from_head()

        repo.checkout_parent()
        parent = repo.get_hash_from_head()

        commit_hashes = [head, parent]
        run_objs = {}

        result = Run.run(
            conf, range_spec=commit_hashes, bench=bench,
            machine_defaults=machine_defaults, _returns=run_objs)
        if result:
            return result

        tabulated = []
        for commit_hash in commit_hashes:
            subtab = {}
            for benchmark in run_objs['benchmarks']:
                subtab[benchmark] = 0.0

            for env in run_objs['environments']:
                filename = results.get_filename(
                    run_objs['machine_params']['machine'], commit_hash, env)
                filename = os.path.join(conf.results_dir, filename)
                result = results.Results.load(filename)

                for benchmark in run_objs['benchmarks']:
                    subtab[benchmark] += result.results[benchmark]

            for benchmark in run_objs['benchmarks']:
                subtab[benchmark] /= len(run_objs['environments'])

            tabulated.append(subtab)

        after, before = tabulated

        table = []
        slowed_down = False
        for name, benchmark in six.iteritems(run_objs['benchmarks']):
            change = after[name] / before[name]
            if change > factor or change < 1.0 / factor:
                table.append(
                    (change, before[name], after[name], name, benchmark))
            if change > factor:
                slowed_down = True

        print()

        if not len(table):
            color_print("BENCHMARKS NOT SIGNIFICANTLY CHANGED.\n", 'green')
            return 0

        table.sort(reverse=True)

        color_print("SOME BENCHMARKS HAVE CHANGED SIGNIFICANTLY.\n", 'red')
        print()
        color_print(
            "{0:40s}   {1:>8}   {2:>8}   {3:>8}\n".format("BENCHMARK", "BEFORE", "AFTER", "FACTOR"),
            'blue')
        for change, before, after, name, benchmark in table:
            before_display = util.human_value(before, benchmark['unit'])
            after_display = util.human_value(after, benchmark['unit'])

            print("{0:40s}   {1:>8}   {2:>8}   {3:.8f}x".format(
                truncate_left(name, 40),
                before_display, after_display, change))

        color_print(
            "SOME BENCHMARKS HAVE CHANGED SIGNIFICANTLY.\n", 'red')

        return slowed_down
