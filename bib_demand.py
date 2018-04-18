#!/usr/bin/env python3

"""
Filename: bib_demand.py
Author: Henning Gebhard

This script is pubslished under CC0 (http://creativecommons.org/publicdomain/zero/1.0/):
To the extent possible under law, Henning Gebhard has waived all copyright and related or
neighboring rights to bib_demand.py. 
"""


import re


class InvalidDataTypeError(ValueError):
    """We can not parse unknown data format."""


class LitItem:
    def __init__(self, data, data_type='ris'):
        if data_type == 'ris':
            self.data = self.__extract_ris(data)
        elif data_type == 'tricat':
            self.data = self.__extract_tricat(data)
        else:
            raise InvalidDataTypeError("I don't know how to parse data_type: {}".format(data_type))

    def get_title(self):
        return self.data.get('T1', 'kein Titel').replace('\n', ' ').strip()

    def get_year(self):
        year = self.data.get('PY', 'kein Jahr')
        if not year:
            year = 'kein Jahr'
        else:
            year = year.replace('[', '').replace(']', '').strip()
        return year

    def get_author(self):
        author = self.data.get('A1', '').replace('\n', ' ').strip()
        if not author:
            author = self.data.get('A2', 'kein Autor').replace('\n', ' ').strip()
        return author

    def get_relevant(self):
        return {
            'author': self.get_author(),
            'title': self.get_title(),
            'year': self.get_year()
        }

    def __eq__(self, other):
        return (self.get_title() == other.get_title() and self.get_year() == other.get_year())

    def __str__(self):
        return '{}\n{}\n{}\n'.format(self.get_author(), self.get_title(), self.get_year())

    def __extract_tricat(self, data):
        """Tricate provides a plain text file when exporting bibliography search results.
        We need a dictionary with relevant data to create a LitItem.
        """
        return {
            'A1': data.get('author'),
            'T1': ' '.join([data.get('title', ''), data.get('subtitle', '')]),
            'PY': data.get('year'),
        }

    def __extract_ris(self, data):
        d = {}
        current_datum = ''
        current_key = ''
        pattern = re.compile('(\S\S)\s\s-(.*)')
        for line in data.split('\n'):
            m = re.match(pattern, line)
            # A match means that we are at the beginning of a section.
            if m:
                # Save previous section
                if current_key:
                    d[current_key] = current_datum
                # Now start the new section
                current_key = m.groups()[0]
                current_datum = m.groups()[1]
            else:
                # No match means we just expand the previous section with the complete current line.
                current_datum += '\n'
                current_datum += line
        # The last section still has to be saved.
        d[current_key] = current_datum
        return d


class Bibliography:
    def __init__(self, filepath=None, data_type='ris'):
        if filepath:
            if data_type == 'ris':
                self.items = self.__read_ris_file(filepath)
            elif data_type == 'tricat':
                self.items = self.__read_tricat_file(filepath)
            else:
                raise InvalidDataTypeError("I don't know how to parse data_type: {}".format(data_type))
        else:
            self.items = []

    def __contains__(self, item):
        if not isinstance(item, LitItem):
            raise ValueError("{} is not a valid LitItem".format(item))
        for containing in self.items:
            if item == containing:
                return True
        return False
    
    def __len__(self):
        return len(self.items)

    def __str__(self):
        return '\n'.join([str(item) for item in self.items])

    def __read_tricat_file(self, filepath):
        items = []

        with open(filepath, encoding='utf-8') as f:
            all_lines = f.readlines()
            line_count = len(all_lines)
            line_number = 0
            current_data = {}

            while line_number < line_count:
                line = all_lines[line_number]

                if line.lstrip().startswith('Jahr'):
                    current_data['year'] = line.replace('Jahr', '', 1).strip()
                    line_number += 1
                elif line.lstrip().startswith('Haupttitel'):
                    data, offset = self.__accumulate_tricat_lines(all_lines, line_number)
                    current_data['title'] = data
                    line_number += offset
                elif line.lstrip().startswith('Titelzusatz'):
                    data, offset = self.__accumulate_tricat_lines(all_lines, line_number)
                    current_data['subtitle'] = data
                    line_number += offset
                elif line.lstrip().startswith('1. Person'):
                    # Whenever we hit on '1. Person' we know that a new item starts.
                    # So we commit the data we currently have and start a new item.
                    if current_data:
                        items.append(LitItem(current_data, data_type='tricat'))
                        current_data = {}
                    data, offset = self.__accumulate_tricat_lines(all_lines, line_number)
                    current_data['author'] = data
                    line_number += offset
                else:
                    line_number += 1

            # Commit the last entry
            items.append(LitItem(current_data, data_type='tricat'))

        return items

    def __accumulate_tricat_lines(self, lines, line_number):
        """From the starting line, add all further lines until we hit an empty line
        or the end of the file. Return the combined data as string and the number
        of lines we combined.
        """
        data = []
        count = len(lines)
        while lines[line_number].strip() and line_number < count:
            line = lines[line_number]
            if line.lstrip().startswith('Haupttitel'):
                line = line.replace('Haupttitel', '', 1)
            elif line.lstrip().startswith('Titelzusatz'):
                line = line.replace('Titelzusatz', '', 1)
            elif line.lstrip().startswith('1. Person'):
                line = line.replace('1. Person/Fam.', '')
            line = line.strip()
            line = line.replace('\n', '')
            data.append(line)
            line_number += 1
        return (' '.join(data), len(data))


    def __read_ris_file(self, filepath):
        with open(filepath, encoding='utf-8') as f:
            data = f.read()
            sections = self.__split_ris(data)
            items = [LitItem(section) for section in sections]
            return items

    def __split_ris(self, data):
        """data is a long string of ris entries. We need to split on empty lines."""
        return data.split('\n\n')

    def intersect(self, other):
        """Build the intersection of two Bibliographies."""
        intersection = Bibliography()
        intersection.items = [item for item in self.items if item in other.items]
        return intersection
    
    def difference(self, other):
        """Build a Bibliography with the difference of items."""
        difference = Bibliography()
        difference.items = [item for item in self.items if item not in other.items]
        return difference
    
    def unique(self):
        """Build a new Bibliography without duplicate items."""
        unique = []
        for item in self.items:
            if item not in unique:
                unique.append(item)
        bib = Bibliography()
        bib.items = unique
        return bib
    
    def order_by(self, attr='title'):
        if attr == 'title':
            sorted_items = sorted(self.items, key=lambda item: item.get_title())
        elif attr == 'author':
            sorted_items = sorted(self.items, key=lambda item: item.get_author())
        elif attr == 'year':
            sorted_items = sorted(self.items, key=lambda item: item.get_year())
        else:
            raise ValueError('{} is not a valid attr argument.'.format(attr))
        bib = Bibliography()
        bib.items = sorted_items
        return bib

    def write_to_file(self, filepath, header=''):
        with open('results/'+filepath, 'w', encoding='utf-8') as f:
            length = str(len(self))
            f.write(header + ' (' + length + ')\n\n')
            f.write(str(self))


def main():
    import sys

    a = 'gesammelte.txt' if len(sys.argv) != 3 else sys.argv[1]
    b = 'neu_tib_gvk_swb.txt' if len(sys.argv) != 3 else sys.argv[2]

    tricat = Bibliography(a, 'tricat')
    print('Items created from %s: %d' % (a, len(tricat)))
    tri_uni = tricat.unique()
    tri_uni = tri_uni.order_by('title')
    print('Unique items in %s: %d' % (a, len(tri_uni)))
    bibl = Bibliography(b, 'ris')
    print('Items created from %s: %d' % (b, len(bibl)))
    bib_uni = bibl.unique()
    bib_uni = bib_uni.order_by('title')
    print('Unique items in %s: %d' % (b, len(bib_uni)))
    intersection = tri_uni.intersect(bib_uni)
    print('Items in the intersection: %d' % (len(intersection)))
    diff = bib_uni.difference(tri_uni)
    print('Items from the bibliography, which are NOT in tricat: %d' % (len(diff)))

    # Write ALL the files!
    tri_uni.write_to_file('tricat_unique.txt', 'Unique items from gesammelte.txt')
    bib_uni.write_to_file('bibl_unique.txt', 'Unique items from neu_tib_gvk_swb.txt')
    intersection.write_to_file('intersection.txt', 'Intersection items')
    diff.write_to_file('difference.txt', 'Missing items in the tricat')

    return tri_uni, bib_uni, intersection, diff

if __name__ == '__main__':
    main()
