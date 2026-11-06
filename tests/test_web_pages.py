import unittest

from mulita.servers.web_pages import (breadcrumbs, directory_content, download_links, file_row,
                                      folder_title, home_content, render_page, shared_resources)


class DirectoryPageTests(unittest.TestCase):
    def test_folder_title_uses_friendly_names_for_top_sections(self):
        self.assertEqual(folder_title([]), 'Archivos')
        self.assertEqual(folder_title(['archivos']), 'Archivos de prueba')
        self.assertEqual(folder_title(['capturas']), 'Capturas e informes')
        self.assertEqual(folder_title(['otra']), 'otra')
        self.assertEqual(folder_title(['capturas', 'ping']), 'ping')

    def test_breadcrumbs_link_every_level_and_point_to_parent(self):
        crumbs, parent = breadcrumbs(['capturas', 'ping'])
        self.assertIn('href="/capturas/"', crumbs)
        self.assertIn('href="/capturas/ping/"', crumbs)
        self.assertIn('Capturas e informes', crumbs)
        self.assertEqual(parent, '/capturas/')
        self.assertEqual(breadcrumbs(['archivos'])[1], '/')
        self.assertEqual(breadcrumbs([])[1], '/')

    def test_breadcrumbs_escape_names(self):
        crumbs, _ = breadcrumbs(['a<b>'])
        self.assertNotIn('<b>', crumbs)
        self.assertIn('a%3Cb%3E', crumbs)

    def test_file_row_describes_folders_files_and_unknown_sizes(self):
        folder = file_row('datos', True, None)
        self.assertIn('Carpeta · Abrir', folder)
        self.assertIn('href="datos/"', folder)
        self.assertNotIn(' download', folder)
        sized = file_row('a b.txt', False, 1234567)
        self.assertIn('1.234.567 bytes · Descargar', sized)
        self.assertIn('href="a%20b.txt" download', sized)
        self.assertIn('Archivo · Descargar', file_row('x', False, None))

    def test_file_row_escapes_the_visible_name(self):
        self.assertIn('&lt;script&gt;', file_row('<script>', False, 1))
        self.assertNotIn('<script>', file_row('<script>', False, 1))

    def test_directory_content_counts_entries_and_handles_empty_folders(self):
        content = directory_content(['archivos'], [('a', False, 1), ('b', True, None)])
        self.assertIn('2 elementos', content)
        self.assertIn('Archivos de prueba', content)
        self.assertIn('Volver al nivel anterior', content)
        empty = directory_content(['archivos', 'vacia'], [])
        self.assertIn('Esta carpeta está vacía.', empty)
        self.assertIn('0 elementos', empty)


class HomePageTests(unittest.TestCase):
    def test_shared_resources_depend_on_capabilities(self):
        self.assertEqual(shared_resources(False, False), '')
        with_captures = shared_resources(True, False)
        for href in ('/capturas/', '/actividad/', '/bitacora/'):
            self.assertIn(f'href="{href}"', with_captures)
        self.assertNotIn('/control', with_captures)
        self.assertIn('href="/control"', shared_resources(False, True))

    def test_download_links_offer_three_sizes(self):
        links = download_links()
        for mb in (1, 10, 100):
            self.assertIn(f'href="/prueba/{mb}"', links)

    def test_home_content_escapes_client_and_server(self):
        content = home_content('HTTP', '<x>', '10.0.0.1', '2026-01-01 00:00:00', False, False)
        self.assertIn('&lt;x&gt;', content)
        self.assertIn('10.0.0.1', content)
        self.assertIn('Conexión establecida', content)

    def test_render_page_marks_the_scheme(self):
        self.assertIn(b'HTTPS', render_page('<p>hola</p>', True))
        self.assertIn(b'<p>hola</p>', render_page('<p>hola</p>'))


if __name__ == '__main__':
    unittest.main()
