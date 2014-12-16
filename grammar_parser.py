import sublime
import sublime_plugin
import os
import traceback
from .GrammarParser import GrammarParser


class GrammarParserCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        self.grammars = [["Browse Grammar File...", "Parse document using existing grammar file"]]
        exist_grammars = sublime.load_settings("GrammarParser.sublime-settings").get("grammars")
        if exist_grammars:
            self.grammars += [(os.path.basename(x), x) for x in exist_grammars]
        else:
            self.on_select_grammar(0)
            return
        self.view.window().show_quick_panel(self.grammars, lambda x: sublime.set_timeout(lambda: self.on_select_grammar(x), 10))

    def file_prelist(self, path):
        dir_list = []
        dir_list.append(["[Current Directory]", path])
        if os.path.dirname(path) != path:
            dir_list.append(["[Parent Folder]", os.path.dirname(path)])
        return dir_list

    def on_select_grammar(self, index):
        if index < 0:
            return
        if index == 0:
            initial_dir = sublime.packages_path()
            if self.view.file_name():
                initial_dir = os.path.dirname(self.view.file_name())
            fd = BrowseDialog(initial_dir=initial_dir, on_done=self.on_select_new_grammar)
            fd.browse(prelist=self.file_prelist)
        else:
            self.on_select_new_grammar(grammar=self.grammars[index][1], new_grammar=False)

    def on_select_new_grammar(self, grammar, new_grammar=True):
        settings = sublime.load_settings("GrammarParser.sublime-settings")
        grammars = settings.get("grammars") or []
        if new_grammar and grammar not in grammars:
            grammars = [grammar] + grammars
            grammars = grammars[:10]
            settings.set("grammars", grammars)
            sublime.save_settings("GrammarParser.sublime-settings")

        self.source_view = self.view.window().show_input_panel("Parser selectors:", "", lambda text: self.on_pass_selectors(grammar, text), None, None)

    def on_pass_selectors(self, grammar, selectors):
        sublime.status_message(self.parse_document(grammar, selectors))

    def parse_document(self, grammar, selectors):
        print("[GrammarParser] Using Grammar: %s" % (grammar))
        status_text = "Error occurred while parsing"
        try:
            grammar_file = open(grammar, "r")
            grammar = sublime.decode_value(grammar_file.read())
            parser = GrammarParser(grammar)
            parse_output = parser.parse_grammar(self.view.substr(sublime.Region(0, self.view.size())))
            status_text = ""
            if parse_output["success"]:
                if selectors == "":
                    nodes = parser.find_all()
                elif selectors == "#":
                    selections = self.view.sel()
                    nodes = parser.find_by_region([0, 0])
                    if selections:
                        first_sel = selections[0]
                        if first_sel.empty():
                            nodes = parser.find_by_region([first_sel.begin(), first_sel.end()])
                        else:
                            nodes = parser.find_inside_region([first_sel.begin(), first_sel.end()])
                else:
                    nodes = parser.find_by_selectors(selectors)
                if selectors != "#":
                    status_text = "Parsing got {} tokens".format(len(nodes))
                for node in nodes:
                    if selectors == "#":
                        if status_text == "":
                            status_text += node["name"]
                        else:
                            status_text += " " + node["name"]
                    else:
                        print("#{begin}:{end} => {name}".format_map(node))
                        print("   => {value}".format_map(node))

                print("Total: {} tokens".format(len(nodes)))
            if selectors != "#":
                if status_text != "" and str(parse_output["end"]) == str(self.view.size()):
                    status_text += " in {elapse_time:.2f}s".format(elapse_time=parser.get_elapse_time())
                else:
                    status_text = "Parsing failed [" + str(parse_output["end"]) + "/" + str(self.view.size()) + "] in {elapse_time:.2f}s".format(elapse_time=parser.get_elapse_time())
            print("Ending: " + str(parse_output["end"]) + "/" + str(self.view.size()))
            print("Parsing Time: {elapse_time:.2f}s".format(elapse_time=parser.get_elapse_time()))
        except Exception:
            print(status_text)
            traceback.print_exc()
        return status_text


class BrowseDialog():
    def __init__(self, initial_dir, path_filter=None, selector=None, window=None, on_done=None, on_cancel=None):
        if window is None:
            self.window = sublime.active_window()
        else:
            self.window = window
        if selector is None:
            self.selector = self.default_selector
        else:
            self.selector = selector
        self.path_filter = path_filter
        self.on_done = on_done
        self.on_cancel = on_cancel
        self.initial_dir = initial_dir
        self.prelist = None
        self.postlist = None

    def default_selector(self, path):
        return os.path.isfile(path)

    def get_list(self, path):
        dir_list = []
        if self.prelist is not None:
            dir_list += self.prelist(path)
        for name in os.listdir(path):
            pathname = os.path.join(path, name)
            if not name.startswith(".") and os.path.isdir(pathname) and (self.path_filter is None or self.path_filter is not None and self.path_filter(pathname)):
                dir_list.append(["[" + name + "]", pathname])
        for name in os.listdir(path):
            pathname = os.path.join(path, name)
            if not name.startswith(".") and os.path.isfile(pathname) and (self.path_filter is None or self.path_filter is not None and self.path_filter(pathname)):
                dir_list.append([name, pathname])
        if self.postlist is not None:
            dir_list += self.postlist(path)
        return dir_list

    def browse(self, current_dir=None, prelist=None, postlist=None):
        if current_dir is None:
            current_dir = self.initial_dir
        if prelist is not None and self.prelist is None:
            self.prelist = prelist
        if postlist is not None and self.postlist is None:
            self.postlist = postlist
        self.dir_list = self.get_list(current_dir)
        selected = 0
        if len(self.dir_list) > 1:
            selected = 1
        self.window.show_quick_panel(self.dir_list, self.on_select, 0, selected)

    def on_select(self, index):
        if index < 0:
            if self.on_cancel is not None:
                self.on_cancel()
            return
        path = self.dir_list[index][1]
        if self.selector(path):
            if self.on_done is not None:
                self.on_done(path)
            return
        else:
            sublime.set_timeout(lambda: self.browse(path), 10)
