 #! python3
import jack
import os
import sys
import logging


class VMTranslator(object):

    def __init__(self, filepath):
        # Init logger object first.

        # Create Logger with "VMTranslator"
        self.logger = logging.getLogger("VMTranslator")
        self.logger.setLevel(logging.DEBUG)
        # File handler which logs even debug messages.
        fh = logging.FileHandler('VMTranslator.log')
        fh.setLevel(logging.DEBUG)
        # create console handler with a higher log level.
        ch = logging.StreamHandler(logging.DEBUG)
        ch.setLevel(logging.DEBUG)
        # create formatter and add it to the handlers.
        formatter = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(message)s'
        )
        fh.setFormatter(formatter)
        # add the handlers to the self.logger
        self.logger.addHandler(fh)

        # init basic attributes
        self.filepath = os.path.abspath(filepath)
        self.filedest = os.path.join(
            filepath,
            os.path.basename(filepath) + '.asm'
        )
        self.asm = open(self.filedest, 'w')  # out file.
        self.parsers = []  # list of parsers.
        self.length = 0  # length of out file.
        self.compare_index = 0  # index for comparison operations.

        # translate arguments into asm symbols.
        self.segment = {
            'local': 'LCL',
            'argument': 'ARG',
            'this': 'THIS',
            'that': 'THAT'
        }

        # retrieve correct jump for argument.
        self.compare = {
            'eq': 'D;JEQ',
            'lt': 'D;JGT',
            'gt': 'D;JLT'
        }

        # With logger object, announce that an Assembler has been initialized.
        self.logger.debug("Assembler initialized {}".format(self.filepath))

        # walk filepath and append VMParser object to parsers for each
        # .vm object in directory and subdirectory.
        self.logger.info("walking %s" % self.filepath)

        for folderName, subfolders, filenames in os.walk(self.filepath):
            self.logger.info("Now in %s" % folderName)

            for subfolder in subfolders:
                self.logger.info(
                    "SUBFOLDER OF %s: %s" % (folderName, subfolders)
                )

            for filename in filenames:
                self.logger.info(
                    'FILE INSIDE %s: %s' % (folderName, filename)
                )
                # only open files with .vm extension.
                if filename.endswith('.vm'):
                    self.logger.info('%s opened for parsing.' % (folderName + filename))
                    self.parsers.append(jack.VMParser(os.path.join(folderName, filename)))

    def __len__(self):
        
        return self.length

    def write(self, *commands):
        """Helper method. Writes a series of strings to output
        self.write(
            '@SP',
            'A=M'
        )

        will write '@SP\nA=M\n' to the output file.
        """

        self.length += len(commands)
        if len(commands) == 1:
            self.asm.write(commands[0] + '\n')
        else:
            self.asm.write('\n'.join(commands))
            self.asm.write('\n')

    def writeArithmetic(self, arg1):
        if arg1 not in ('not', 'neg', 'and', 'or', 
            'add', 'sub', 'eq', 'gt', 'lt'):

            return None

        elif arg1 in ('not', 'neg'):
            self.write(
                '@SP',  # Get stack pointer
                'AM=M-1',  # Deincrement sp and A register
                # Invert if 'not' else opposite.
                '%s' % 'M=!M' if arg1 == 'not' else 'M=-M',
                '@SP',  # Get stack pointer
                'AM=M+1'  # increment stack pointer and A register
            )

        elif arg1 == 'add':
            self.write(
                '@SP',
                'AM=M-1',
                'D=M',  # retrieve top of stack.
                'A=A-1',
                'M=D+M'  # retrieve next stack entry, add, and restore.
            )

        elif arg1 == 'sub':
            self.write(
                '@SP',
                'AM=M-1',
                'D=-M', 
                'A=A-1',
                'M=D+M'
            )

        elif arg1 == 'and':
            self.write(
                '@SP',
                'AM=M-1',
                'D=M',
                'A=A-1',
                'M=D&M'
            )

        elif arg1 == 'or':
            self.write(
                '@SP',
                'AM=M-1',
                'D=M',
                'A=A-1',
                'M=D|M'
            )

        elif arg1 in ('eq', 'lt', 'gt'):
            self.write(
                '@SP',
                'AM=M-1',
                'D=M',
                'A=A-1',
                'D=D-M',
                '@TRUE_%d' % self.compare_index,
                '%s' % self.compare[arg1],
                # Implied False clause
                'D=0',
                '@END_CMP_%d' % self.compare_index,
                '0;JMP',
                '(TRUE_%d)' % self.compare_index,
                'D=-1',
                '(END_CMP_%d)' % self.compare_index,
                '@SP',
                'A=M-1',
                'M=D'
            )
            self.compare_index += 1

    def writePushPop(self, commandType, arg1, arg2):

        if commandType not in ('C_PUSH', 'C_POP'):
            return None

        elif commandType == 'C_PUSH':
            # push <arg1> <arg2>
            if arg1 == 'constant':
                # push constant <arg2>
                self.write(
                    '@%d' % arg2,
                    'D=A',
                    '@SP',
                    'A=M',
                    'M=D',
                    '@SP',
                    'AM=M+1'
                )

            elif arg1 == 'temp':
                # push temp <index> onto
                self.write(
                    '@R%d' % (5 + arg2),
                    'D=M',
                    '@SP',
                    'A=M',
                    'M=D',
                    '@SP',
                    'AM=M+1'
                )

            elif arg1 == 'static':
                self.write(
                    '@%d' % (16 + arg2),
                    'D=M',
                    '@SP',
                    'A=M',
                    'M=D',
                    '@SP',
                    'AM=M+1'
                )

            elif arg1 in ('local', 'argument', 'this', 'that'):
                self.write(
                    '@%d' % arg2,
                    'D=A',
                    '@%s' % self.segment[arg1],
                    'A=D+M',  # Go to the base + index address.
                    'D=M',
                    '@SP',
                    'A=M',
                    'M=D',
                    '@SP',
                    'AM=M+1'
                )

            elif arg1 == 'pointer':
                self.write(
                    '@%s' % ('THIS' if arg2 == 0 else 'THAT'),
                    'D=M',
                    '@SP',
                    'A=M',
                    'M=D',
                    '@SP',
                    'AM=M+1'
                )

        else:  # C_POP
            if arg1 == 'temp':
                self.write(
                    '@SP',
                    'AM=M-1',
                    'D=M',
                    '@R%d' % (5 + arg2),
                    'M=D'
                )

            elif arg1 == 'static':
                self.write(
                    '@SP',
                    'AM=M-1',
                    'D=M',
                    '@%d' % (16 + arg2),
                    'M=D'
                )

            elif arg1 in ('local', 'argument', 'this', 'that'):
                self.write(
                    '@%s' % self.segment[arg1],
                    'D=M',
                    '@%d' % arg2,
                    'D=D+A',
                    '@R13',
                    'M=D',
                    '@SP',
                    'AM=M-1',
                    'D=M',
                    '@R13',
                    'A=M',
                    'M=D'
                )

            elif arg1 == 'pointer':
                self.write(
                    '@SP',
                    'AM=M-1',
                    'D=M',
                    '@%s' % ('THIS' if arg2 == 0 else 'THAT'),
                    'M=D'
                )            

    def writeInit(self):
        pass

    def writeLabel(self, label):
        pass

    def writeGoto(self, label):
        pass

    def writeIf(self, label):
        pass

    def writeCall(self, functionName, numArgs):
        pass

    def writeReturn(self):
        pass

    def writeFunction(self, functionName, numLocals):
        pass

    def close(self):
      
        self.file.close()

    def translate(self):
        
        # loop over each parser for each .vm file.
        self.logger.info("Iter over parsers.")
        for parser in self.parsers:
            self.logger.info('Parser of {}'.format(parser.filepath))

            for command, commandType, arg1, arg2 in parser:
                self.logger.info('Current command: %s' % command)
                self.logger.debug('%s %s %s' % (commandType, arg1, arg2))

                if commandType == parser.C_ARITHMETIC:
                    self.writeArithmetic(arg1)
                elif commandType in (parser.C_PUSH, parser.C_POP):
                    self.writePushPop(commandType, arg1, arg2)

        self.asm.close()

if __name__ == '__main__':

    while True:

        try:
            print("Enter filepath. Relative paths to the cwd are acceptable.")
            filepath = input()
            if not os.path.exists(filepath):
                raise IOError

            V = VMTranslator(filepath)

        except IOError:
            print("IOError. Enter real filepath")
            continue

        break

    V.translate()
    print(".asm file generated.")
    sys.exit()
    quit()
