"""
/******************************************************************************

   Copyright 2003-2018 AMIQ Consulting s.r.l.

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

******************************************************************************/
/******************************************************************************
   Original Authors: Teodor Vasilache and Dragos Dospinescu,
                     AMIQ Consulting s.r.l. (contributors@amiq.com)

               Date: 2018-Oct-07
******************************************************************************/
"""
import os
import sys
import xml.etree.ElementTree as ET
from fnmatch import fnmatch

"""
Description of the UCIS DB hierarchy generated by the current FC4SC implementation:

UCIS top level element
|
-> instanceCoverages [0:n]
   |  moduleName : name of the covergroup type
   |
   -> cgInstance [0:n]
      |  name : name of the covergroup instance
      |
      -> coverpoint [0:n]
      |  |  name : name of the coverpoint
      |  |
      |  -> coverpointBin [0:n]
      |     | name : name of the bin
      |     | type : the type of bin (default/ignore/illegal)
      |     |
      |     -> range [0:n]
      |        | from : start value of the interval
      |        | to   : end value of the interval
      |        |
      |        -> contents 
      |           | coverageCount : the number of hits registered in this interval
      |           0
      | 
      -> cross [0:n]
         | name : name of the cross
         |
         -> crossBin [0:n]
            | name : name of the cross bin
            | 
            -> index
            -> index 
            .
            .     Number of indexes = number of crossed coverpoints
            .
            -> index  
            | 
            -> contents                                                        
               | coverageCount : the number of hits registered in this cross bin
               0                                                               
            
Note that this only contains the elements which are relevant for merging!

Merging steps:
 1) Parse covergroup types: for each "instanceCoverages" element:
        if this element does not exist in the mergeDBtree:
            add this element to the mergeDBtree directly under the root element
        else: goto step 2
    Note: same covergroup type condition: equality of the 'moduleName' attribute 
        
 2) Parse covergroup instances: for each "covergroupCoverage/cgInstance" element:
        if this element does not exist in the "covergroupCoverage" element of mergeDBtree:
            add this element under the "covergroupCoverage" element 
        else: goto step 3
    Note: same covergroup instance condition: equality of the 'name' attribute
            
 3) Parse coverpoints: for each "coverpoint" element:
        if this element does not exist in the "cgInstance" element of mergeDBtree:
            raise exception: coverpoint not present in the mergeDBtree! 
        else: goto step 4
    Note: same coverpoint condition: equality of the 'name' attribute
    
 4) Parse bins: for each "bin" element:
        if this element does not exist in the "coverpoint" element of mergeDBtree:
            add this element under the "coverpoint" element 
        else: goto step 5
    Note: same bin condition: equality of the 'name' attribute
    
 5) Sum the bin ranges' hit counts: for each "range" element:
        if this element does not exist in the "bin" element:
            raise exception: bin is different than expected!
        else:
            add to the coverageCount
    Note: same range condition: equality of the 'name' attribute
    Note2: if 2 bins have the same name, but of different from, to or type attribute values => error

 6) Parse crosses: for each "cross" element:
        if this element does not exist in the "cgInstance" element of mergeDBtree:
            raise exception: cross not present in the mergeDBtree! 
        else: goto step 7
    Note: same cross condition: equality of the 'name' attribute
    
 7) Parse crosses bins: for each "crossBin" element:
        if this element does not exist in the "cross" element of mergeDBtree:
            add this element under the "cross" element 
        else: goto step 8
    Note: same crossBin condition: the list of index elements have the same value, in the
    same order
        
"""
class UCIS_DB_Parser:
    def __init__(self):
        self.ucis_ns = 'ucis'
        self.ucis_ns_schema = 'http://www.w3.org/2001/XMLSchema-instance'
        # namespace map
        self.ns_map = {self.ucis_ns : self.ucis_ns_schema}
        # register the UCIS namespace
        ET.register_namespace(self.ucis_ns, self.ucis_ns_schema)
        self.ucis_db = {
            "instanceCoverages"  : '{0}:instanceCoverages' .format(self.ucis_ns),
            "covergroupCoverage" : '{0}:covergroupCoverage'.format(self.ucis_ns),
            "cgInstance"         : '{0}:cgInstance'        .format(self.ucis_ns),
            "coverpoint"         : '{0}:coverpoint'        .format(self.ucis_ns),
            "coverpointBin"      : '{0}:coverpointBin'     .format(self.ucis_ns),
            "range"              : '{0}:range'             .format(self.ucis_ns),
            "contents"           : '{0}:contents'          .format(self.ucis_ns),
            "cross"              : '{0}:cross'             .format(self.ucis_ns),
            "crossBin"           : '{0}:crossBin'          .format(self.ucis_ns),
            "crossExpr"          : '{0}:crossExpr'         .format(self.ucis_ns),
            "index"              : '{0}:index'             .format(self.ucis_ns),
            "userAttr"           : '{0}:userAttr'          .format(self.ucis_ns)
        }
        # the master ucis DB which will be "merged" into when parsing additional DBs
        self.mergeDBtree = None
        self.mergeDBroot = None
    
    def pre_write_operations(self):
        """
        FIXME: Known problems
        1) Some Coverpoint bins can be present in one covergroup instance, but not in another.
        In other words, different covergroup instances of the the same type can have bins which 
        might not be present in a certain coverpoint. This creates a problem when merging crosses, 
        as the current implementation does NOT account for this case!
        
        2) Top level UCIS element attributes of the resulted merged DB have to be updated!
        ====================
        parentId="200" 
        logicalName="string" 
        physicalName="string" 
        kind="string" 
        testStatus="true" 
        simtime="1.051732E7" 
        timeunit="string" 
        runCwd="string" 
        cpuTime="1.051732E7" 
        seed="string" 
        cmd="string" 
        args="string" 
        compulsory="string" 
        date="2004-02-14T19:44:14" 
        userName="string" 
        cost="1000.00" 
        toolCategory="string" 
        ucisVersion="string" 
        vendorId="string" 
        vendorTool="string" 
        vendorToolVersion="string" 
        sameTests="42" 
        comment="string"
        ====================
        
        3) parse the resulted DB and change the "UCIS ID" attributes to be unique
         can use an ElementTree tree walker for this task!
        """
        pass
    
    def write_merged_db(self, merged_db_path):
        self.pre_write_operations()
        self.mergeDBtree.write(file_or_filename = merged_db_path,
                  encoding = "UTF-8", 
                  xml_declaration = True)
        
    def process_xml(self, filename):
        parseTree = ET.parse(filename)
        parseRoot = parseTree.getroot()
        
        tagstr = parseRoot.tag[-len("UCIS"):]
        if tagstr != "UCIS":
            return False
        
        if self.mergeDBtree is None:
            print("First UCIS XML found set as base DB:\n\t{0}\n".format(filename))
            self.mergeDBtree = parseTree
            self.mergeDBroot = self.mergeDBtree.getroot()
        else:
            print("Found XML file: {0}".format(filename))
            # TODO: update exceptions to be more verbose in function parseXML
            # Needed information:
            # Context: full path to element which produces error on parsing
            # Info: error description
            # Source XML files where the element(s) is/are found
            # TODO: surround by try-catch and handle thrown exceptions
            self.parse_xml(parseRoot)
            
        return True
    
    def find_ucis_element(self, element, subElementName):
        return element.find('{0}:{1}'.format(self.ucis_ns, subElementName), self.ns_map)
    
    def findall_ucis_children(self, element, subElementName):
        return element.findall('{0}:{1}'.format(self.ucis_ns, subElementName), self.ns_map)
    
    def parse_xml(self, parseRoot):
        """ 1) Parse covergroup types """
        for instanceCoverages in self.findall_ucis_children(parseRoot, "instanceCoverages"):
            covergroupTypeNameAttrib = 'moduleName'
            covergroupTypeName = instanceCoverages.get(covergroupTypeNameAttrib)
            xpath_query = "./*[@{1}='{2}']/{0}:covergroupCoverage".format(
                self.ucis_ns, covergroupTypeNameAttrib, covergroupTypeName)
            # search the same element in the resulted merged database
            searchElement = self.mergeDBtree.find(xpath_query, self.ns_map)
    
            print("Parsing covergroup type: {0}".format(covergroupTypeName))
            if searchElement is not None:
                self.parse_covergroup_type(searchElement, xpath_query)
                print("\n")
            else:
                print("Found new coverage type [{0}]".format(covergroupTypeName))
                mergeParent = self.mergeDBroot
                mergeParent.append(instanceCoverages) # add the element to the mergedDB under root element

    def parse_covergroup_type(self, covergroup_type, parent_query):
        """ Parse covergroup instance """
        for cgInstance in self.findall_ucis_children(covergroup_type, "cgInstance"):
            cgInstNameAttrib = 'name'
            cgInstName = cgInstance.get(cgInstNameAttrib)
            xpath_query = parent_query + "/" + "*[@{0}='{1}']".format(cgInstNameAttrib, cgInstName)
            # search the same element in the resulted merged database
            searchElement = self.mergeDBtree.find(xpath_query, self.ns_map)
            
            if searchElement is not None:
                print ("\t[cgInstance] {0}".format(cgInstName))
                self.parse_coverpoints(cgInstance, xpath_query)
                self.parse_crosses(cgInstance, xpath_query)
            else:
                print("\tFound new coverage instance [{0}]".format(cgInstName))
                mergeParent = self.mergeDBtree.find(parent_query, self.ns_map)
                mergeParent.append(cgInstance) # add the element to the covergroup

    def parse_coverpoints(self, cgInstance, parent_query):
        """ Parse coverpoint """
        for coverpoint in self.findall_ucis_children(cgInstance, "coverpoint"):
            cvpNameAttrib = 'name'
            cvpName = coverpoint.get(cvpNameAttrib)
            xpath_query = parent_query + "/" + "*[@{0}='{1}']".format(cvpNameAttrib, cvpName)
            # search the same element in the resulted merged database
            searchElement = self.mergeDBtree.find(xpath_query, self.ns_map)
        
            print ("\t\t[coverpoint] {0}".format(cvpName))
            if searchElement is not None:
                self.parse_coverpoint_bins(coverpoint, xpath_query)
            else:
                raise ValueError("coverpoint not present in the mergeDBtree!")
        
    def parse_coverpoint_bins(self, coverpoint, parent_query):
        """ Parse bins """
        for bin in self.findall_ucis_children(coverpoint, "coverpointBin"):
            binNameAttrib = 'name'
            binName = bin.get(binNameAttrib)
            xpath_query = parent_query + "/" + "*[@{0}='{1}']".format(binNameAttrib, binName)
            binMergeElement = self.mergeDBtree.find(xpath_query, self.ns_map)
            
            if binMergeElement is not None:
                self.merge_bin_hits(bin, binMergeElement, xpath_query)
            else:
                print("\t\tFound new bin [{0}]".format(binName))
                mergeParent = self.mergeDBtree.find(xpath_query + "/..", self.ns_map)
                mergeParent.append(bin) # add the bin to the covergpoint
        
    def merge_bin_hits(self, bin, binMergeElement, parent_query):
        """ Sum the bin ranges' hit counts """
        # merge hits for bins which are present in both the parsed DB and mergeDBtree
        for range in self.findall_ucis_children(bin, "range"):
            contents = range.find('{0}:contents'.format(self.ucis_ns), self.ns_map)
            rangeHitCount = int(contents.get('coverageCount'))
            xpath_query = parent_query + "/" + '{0}:range'.format(self.ucis_ns)
            searchElement = self.mergeDBtree.find(xpath_query, self.ns_map)
            
            if searchElement is None:
                raise ValueError("Range not found! Bin contents differ between mergeDBtree and parsed XML!")
            
            sameFrom = searchElement.get('from') == range.get('from')
            sameTo = searchElement.get('to') == range.get('to')
            
            if not (sameFrom and sameTo):
                raise ValueError("Range limits differ between mergeDBtree and parsed XML!")
            
            mergeContentsElement = self.find_ucis_element(searchElement, 'contents')
            parsedContentsElement = self.find_ucis_element(range, 'contents')
            totalhits = int(mergeContentsElement.get('coverageCount'))
            parsedHits = int(parsedContentsElement.get('coverageCount'))
            totalhits += parsedHits
            
            # NOTE: alias attribute is set in the coverpointBin element because the
            # javascript gui application uses this field for showing the number of hits! 
            binMergeElement.set('alias', str(totalhits))
            mergeContentsElement.set('coverageCount', str(totalhits))
    
        print ("\t\t\t[bin:{1}] {0} -> {2}".format(
            bin.get('name'), bin.get('type'), totalhits))    
        
    def parse_crosses(self, cgInstance, parent_query):
        for cross in self.findall_ucis_children(cgInstance, "cross"):
            crossNameAttrib = 'name'
            crossName = cross.get(crossNameAttrib)
            xpath_query = parent_query + "/" + "*[@{0}='{1}']".format(crossNameAttrib, crossName)
            mergeCrossElement = self.mergeDBtree.find(xpath_query, self.ns_map)
            
            print ("\t\t[cross] {0}".format(crossName))
            if mergeCrossElement is None:
                raise ValueError("cross not present in the mergeDBtree!")
                continue # skip processing the sub-elements
            
            # skip processing crosses with no hits in the parse XML
            if self.find_ucis_element(cross, 'crossBin') is None:
                print("\t\t\tParsed cross is empty; skipping...")
                continue
             
            # the number of coverpoints crossed by this element
            numCvps = len(self.findall_ucis_children(mergeCrossElement, 'crossExpr'))
            """ Parse cross bins """
            mergeMap = {}
            
            # parse the mergeDBtree and store all existing cross bins and their associated hit count
            # then, parse the current XML and update the map with the new information
            # then, remove all the the crossBin elements from the cross
            # then, create new crossBins elements matching the information stored in the map!
            for crossBin in self.findall_ucis_children(mergeCrossElement, 'crossBin'):
                binIndexes = []
                for index in self.findall_ucis_children(crossBin, 'index'):
                    binIndexes.append(int(index.text))
                
                contentsElement = self.find_ucis_element(crossBin, 'contents')
                hitCount = int(contentsElement.get('coverageCount'))
                
                if len(binIndexes) != numCvps:
                    raise ValueError("Found crossBin of bigger size than the number of coverpoints!") 
                
                tupleIndexes = tuple(binIndexes)
                mergeMap[tupleIndexes] = hitCount
                # remove crossBin
                mergeCrossElement.remove(crossBin)
            
            for crossBin in self.findall_ucis_children(cross, 'crossBin'):
                binIndexes = []
                for index in self.findall_ucis_children(crossBin ,'index'):
                    binIndexes.append(int(index.text))
                
                contentsElement = self.find_ucis_element(crossBin, 'contents')
                hitCount = int(contentsElement.get('coverageCount'))
                
                tupleIndexes = tuple(binIndexes)
                if tupleIndexes in mergeMap:
                    mergeMap[tupleIndexes] = mergeMap[tupleIndexes] + hitCount
                else:
                    mergeMap[tupleIndexes] = hitCount
            
            crossBinString = """<{0}:crossBin name="" key="0" type="default" xmlns:{0}="{1}">\n"""
            for _ in range(numCvps):
                crossBinString += "<{0}:index>0</{0}:index>\n"
                
            crossBinString += """<{0}:contents coverageCount="0"></{0}:contents>\n"""
            crossBinString += "</{0}:crossBin>\n"
            crossBinString = crossBinString.format(self.ucis_ns, self.ns_map[self.ucis_ns])
                 
            # update crossBins element and append it to the mergeCrossElement
            for indexesTuple in mergeMap:
                # create new crossBin element to be added to the cross
                crossBinElement = ET.fromstring(crossBinString)
                print("\t\t\t" + str(indexesTuple) + " -> " + str(mergeMap[indexesTuple]))
                
                # get a generator for the index elements contained by this crossBin;
                # we will need to manually iterate through this generator when updating the indexes
                indexElementGen = iter(self.findall_ucis_children(crossBinElement, 'index'))
                for i in range(len(indexesTuple)):
                    # update index element value
                    indexElementValue = indexesTuple[i]
                    indexElement = next(indexElementGen)
                    indexElement.text = str(indexElementValue)
                    
                # update the contents element with the merged data
                contentsElement = self.find_ucis_element(crossBinElement, 'contents')
                contentsElement.set('coverageCount', str(mergeMap[indexesTuple]))
                # add the contents element to the cross in the mergeDBtree
                mergeCrossElement.append(crossBinElement)
                
            # move the user attribute element to the end of the cross
            userAttrElement = self.find_ucis_element(mergeCrossElement, 'userAttr')
            mergeCrossElement.remove(userAttrElement)
            mergeCrossElement.append(userAttrElement)
            

def find_xmls(directory):
    for rootdir, _, files in os.walk(directory):
        for fname in files:
            if fnmatch(fname, '*.xml'):
                filename = os.path.join(rootdir, fname)
                yield filename
                
if __name__ == "__main__":
    # the search top directory is by default the execution directory 
    search_top_dir = os.getcwd()
    merged_db_name = "coverage_merged_db.xml"
    if len(sys.argv) > 1: # if specified file path
        search_top_dir = sys.argv[1]
    if len(sys.argv) > 2: # if specified merged database name
        merged_db_name = sys.argv[2]

    print("Searching for XMLs in top directory: \n{0}\n".format(search_top_dir))
    merged_db_path = os.path.join(search_top_dir, merged_db_name)
    
    # the master ucis DB which will be "merged" into when parsing additional DBs
    merger = UCIS_DB_Parser()

    # list of the file names that are successfully parsed and merged
    filelist = []
    for filename in find_xmls(search_top_dir):
        # found file matches the output file; skip it
        if filename == merged_db_path:
            print("Warning! Input File: \n{0}\nmatches output target file => will not be parsed!".format(filename))
            continue
        
        if not merger.process_xml(filename):
            print("Non-UCIS DB XML file skipped [{0}]".format(filename))
            continue
            
        filelist.append(filename)
        
    if not filelist:
        print("Error! No XML files found under " + search_top_dir)
        exit(1)
    
    merger.write_merged_db(merged_db_path)

    print("Done!");
    print("Searching was done recursively under directory: \n{0}\n".format(search_top_dir))
    
    print("List of merged UCIS DB files:")
    for f in filelist:
        print(f)
        
    print("\nResulted merged UCIS DB can be found at:\n" + merged_db_path)