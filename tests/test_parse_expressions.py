from qdagview3.evaluate_python import find_unbounded_names
import ast
import unittest

class TestExpressions(unittest.TestCase):
    def test_expressions(self):
        expr = "y + z"
        self.assertEqual( find_unbounded_names(expr),  ['y', 'z']) 

    def test_list_comprehension(self):
        expr = '[item for item in items]'
        self.assertEqual( find_unbounded_names(expr),  ['items']) 

    def test_generator_comprehension(self):
        expr = '(num for num in numbers)'
        self.assertEqual( find_unbounded_names(expr),  ['numbers']) 

    def test_tuple_unpacking(self):
        expr = '[(key, value) for key, value in data.items()]'
        self.assertEqual( find_unbounded_names(expr),  ['data']) 

    def test_dict_comprehension(self):
        expr = '{key: value for key, value in data.items()}'
        tree = ast.parse(expr)
        self.assertEqual( find_unbounded_names(expr),  ['data'], msg=ast.dump(tree, indent=4))

    def test_range_comprehension(self):
        expr = '[x for x in range(10)]'
        unbound_names = find_unbounded_names(expr)
        self.assertEqual( unbound_names,  [])

if __name__ == "__main__":
    unittest.main()
